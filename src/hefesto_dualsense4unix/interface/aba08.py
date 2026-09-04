# A PASTA, não /tmp: estas três liam um `monta` de /tmp — o de 26/08 23:50 —
# que por sua vez lia um `topo.html` de /tmp parado às 10:59. Três das dez
# abas vinham de um montador e de um esqueleto de ontem, e nenhuma correção
# no topo.html desta pasta as alcançava. Achado em 27/08.
import ast
import html
import importlib.util
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde  # noqa: E402
from monta import (DS, MESA, CONECTADOS, CSS_GLIFO, CSS_POPUP, cor_da_zona,  # noqa: E402
                   glifo, monta, player_slot_color, svg)

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA. Medido em 28/08/2026: oito
# arquivos desta casa cravavam o caminho absoluto da árvore DELA, e por isso
# rodar uma CÓPIA do gerador REESCREVIA o mockup dela. Aconteceu numa prova:
# o `05-vibracao.html` dela ficou com `--r-motor:56px` porque um agente rodou
# uma cópia noutro diretório. É o mesmo estrago de 25/08, quando o mockup que
# ela ia abrir sumiu do disco na frente dela — e é o que impediria qualquer
# segunda árvore de trabalhar sem tocar na primeira.
# A RAIZ TEM DONO, e é o `onde.py`. Ela era `parents[2]` aqui — o que dava
# a pasta `src/` depois que a interface se mudou para dentro dela em
# 01/09/2026, e fazia toda leitura de fonte procurar em `src/src/…`. Os
# geradores 08 e 09 pararam de RODAR por isso, calados até alguém tentar:
# `FileNotFoundError: .../src/src/hefesto_dualsense4unix/app/actions/...`.
# O contador de níveis é o defeito que o `onde.py` existe para não repetir.
from onde import RAIZ as R  # noqa: E402

# A CAMADA DE TELA DESTA ABA, que já existe no produto e nunca foi ligada.
# Daqui sai a lista de respostas do "— O que é? —": ver `VIZINHOS`, abaixo.
from hefesto_dualsense4unix.gui import aba_conexoes as _aba_conexoes  # noqa: E402

# OS DOIS DONOS DO VEREDITO DO CHECK-UP — decisão D-16 dela, 04/09/2026.
# `ordens_da_mesa.cabecalho` escreve as QUATRO frases possíveis do topo e
# `exame_da_mesa.veredito` decide a cor. Os dois são puros e importam sem
# `structlog`, que é o que separa este par do `secao_exame` (ele puxa
# `escritor_cru`, que puxa o logger, e o `python3 aba08.py` desta pasta não roda
# no `.venv`). Ver `VEREDITO_DO_DESENHO`, abaixo.
from hefesto_dualsense4unix.integrations import exame_da_mesa as _exame_da_mesa  # noqa: E402
from hefesto_dualsense4unix.integrations import ordens_da_mesa as _ordens_da_mesa  # noqa: E402

# O PACOTE DESTA ABA — e ele é DONO de três coisas que os dois lados desenham:
# o rótulo do controle, a tinta legível sobre o plástico e a régua do rádio.
# Mesma dependência que o `aba04.py` já tem do `pacotes.a04_iluminacao`, e pela
# mesma razão: enquanto o desenho e o produto escreverem a mesma frase duas
# vezes, elas divergem sem que ninguém veja.
from pacotes import a08_conexoes as _pacote08  # noqa: E402

# ---------------------------------------------------------------------------
# OS NÚMEROS DO PRODUTO VÊM DO PRODUTO, LIDOS POR AST.
#
# Eles estavam digitados nesta tela: `1.600`, `260,4`, `276,7`, `16,3`, `553`,
# `830`, `1.107` — sete literais, e nenhuma régua sabia dizer se algum deles
# ainda batia com a medição. É o mesmo defeito que o `PADRAO_JOGADOR` do
# `monta.py` tinha (o jogador 3 escrito `"234"` quando o canônico é `"135"`), e
# a cura é a mesma: deixar de ter um literal.
#
# E O DEFEITO ESTAVA VIVO NUM OITAVO NÚMERO, achado em 28/08: a dica do teto da
# vibração dizia *"«Bateria longa» corta a força em 60%"*. O produto corta em
# **30%** — `RUMBLE_POLICY_MULT["economia"] = 0.3`, e é dele que
# `secao_orcamento` deriva a frase da tela, com o cuidado escrito no próprio
# arquivo: *"escrever «30%» à mão nesta tela"* é o que ele existe para evitar.
# O 60 era o dobro do limite real, e nenhuma régua podia vê-lo. Agora ele
# também é derivado.
#
# POR AST E NÃO POR IMPORT, e o motivo é medido: `radio_da_mesa` puxa
# `structlog` por `core.sysfs_leds`, e o `python3 abaNN.py` desta pasta não roda
# no `.venv`. É exatamente o que `scripts/validar-fala-de-tela.py` já faz com o
# mesmo módulo, e pela mesma razão — "nunca importando este módulo".
# ---------------------------------------------------------------------------
def _valor(no, ja):
    """O valor de um nó de AST, resolvendo NOME contra o que já foi lido.

    `ast.literal_eval` sozinho não dá conta de `{PERFIL_TUDO_LIGADO: "Tudo
    ligado"}` — a chave é um `Name`, não um literal, e a chamada estoura. Como
    o módulo é lido de cima para baixo, o nome já está no `ja` quando a linha
    que o usa aparece; é a mesma leitura que o interpretador faria, sem
    executar nada.
    """
    if isinstance(no, ast.Name):
        return ja[no.id]
    if isinstance(no, ast.Attribute):
        #: `mapa_das_portas.LACUNA_POSICAO` vira `"LACUNA_POSICAO"` — o NOME da
        #: chave, não o valor dela (que mora noutro módulo). É o bastante para o
        #: que esta tela precisa: a `CONFISSAO` do produto é um dicionário cujas
        #: CHAVES são atributos, e sem esta linha o `literal_eval` estoura e o
        #: dicionário inteiro é engolido pelo `except` — a tela teria de digitar
        #: as cinco frases de novo, que é a segunda verdade que esta casa mata.
        return no.attr
    if isinstance(no, ast.Dict):
        return {_valor(k, ja): _valor(v, ja) for k, v in zip(no.keys, no.values)}
    if isinstance(no, ast.Tuple):
        return tuple(_valor(e, ja) for e in no.elts)
    if isinstance(no, ast.List):
        return [_valor(e, ja) for e in no.elts]
    return ast.literal_eval(no)


def _constantes(caminho, nomes):
    """As constantes de módulo daquele arquivo, lidas sem importar nada.

    Reprova em voz alta quando um nome some: uma constante renomeada no produto
    tem de derrubar a geração da tela, não sumir dela em silêncio.
    """
    arvore = ast.parse(pathlib.Path(caminho).read_text())
    ja, achado = {}, {}
    for no in arvore.body:
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            alvo, valor = no.targets[0], no.value
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvo, valor = no.target, no.value
        else:
            continue
        if not isinstance(alvo, ast.Name):
            continue
        try:
            ja[alvo.id] = _valor(valor, ja)
        except (ValueError, TypeError, KeyError, SyntaxError):
            continue  # o que não é literal não interessa — e não pode parar a leitura
        if alvo.id in nomes:
            achado[alvo.id] = ja[alvo.id]
    if faltam := set(nomes) - set(achado):
        raise SystemExit(f"ERRO: {caminho} não tem mais {sorted(faltam)} — "
                         f"a tela dependia deles.")
    return achado


RADIO = _constantes(
    R / "src/hefesto_dualsense4unix/integrations/radio_da_mesa.py",
    {"SLOTS_POR_SEGUNDO", "SLOTS_POR_RELATORIO", "HZ_INPUT_SEM_MIC",
     "HZ_INPUT_COM_MIC", "HZ_AUDIO_COM_MIC", "CORTE_FOLGADA", "CORTE_APERTADA",
     "PALAVRA_FOLGADA", "PALAVRA_APERTADA", "PALAVRA_CHEIA"})

TETO = RADIO["SLOTS_POR_SEGUNDO"]
CUSTO_SEM_MIC = RADIO["HZ_INPUT_SEM_MIC"] * RADIO["SLOTS_POR_RELATORIO"]
CUSTO_COM_MIC = ((RADIO["HZ_INPUT_COM_MIC"] + RADIO["HZ_AUDIO_COM_MIC"])
                 * RADIO["SLOTS_POR_RELATORIO"])
CUSTO_DO_MIC = CUSTO_COM_MIC - CUSTO_SEM_MIC

# ---------------------------------------------------------------------------
# O TETO DA VIBRAÇÃO — o global e o do controle, com os dois números do produto.
#
# Decisão dela, 28/08: *"nos dois: o global manda, o do controle sobrepõe"*. O do
# controle é novo, e nasce como sprint sobre a `POR-UNIDADE-01` (10/08), que já
# grava política de vibração POR CONTROLE em
# `profiles/manager._controllers_to_rumble_scales`.
#
# O GLOBAL MORAVA AQUI E MUDOU-SE. Ainda no mesmo 28/08 ele foi para a aba
# **Sistema** como **Perfil de Bateria** (ver `CASA_DO_TETO_GLOBAL`, abaixo).
# Esta aba continua LENDO os três perfis do produto — é deles que sai a frase de
# quanto o global vale hoje, que cada linha de controle mostra no `?` —, mas não
# tem mais o campo que os muda.
#
# Os três rótulos e o "Sem teto" são do `secao_orcamento`; o degrau é do
# `RUMBLE_POLICY_MULT`, que é o dono único dele.
# ---------------------------------------------------------------------------
MULT = _constantes(R / "src/hefesto_dualsense4unix/daemon/subsystems/rumble.py",
                   {"RUMBLE_POLICY_MULT"})["RUMBLE_POLICY_MULT"]
#: `SEM_TETO` SAIU DO `secao_orcamento` em 01/09/2026 e está aqui, ao lado do
#: `_ORCAMENTO_COM_TETO` — aquele módulo puxa `gi`/`Gtk` no import, e a camada de
#: tela que precisa da palavra promete não ter GTK. Este `_constantes` reprova em
#: voz alta se ele mudar de casa outra vez, que é o contrato dele.
_RUM = _constantes(R / "src/hefesto_dualsense4unix/core/rumble.py",
                   {"_ORCAMENTO_COM_TETO", "SEM_TETO"})
COM_TETO = _RUM["_ORCAMENTO_COM_TETO"]
ORC = _constantes(R / "src/hefesto_dualsense4unix/app/actions/config/secao_orcamento.py",
                  {"PERFIS", "ROTULOS_DOS_PERFIS", "TETO_POR_PERFIL"})
ORC["SEM_TETO"] = _RUM["SEM_TETO"]

#: A FRASE DO TETO É DO PRODUTO — 01/09/2026. Esta função existia AQUI, com a
#: mesma conta escrita de novo, e agora ela é um ponteiro para
#: `gui.aba_conexoes.fala_do_teto`. Havia TRÊS grafias das mesmas três frases (a
#: desta bancada, as três literais que a `gui/aba_conexoes.py` digitava no HTML e
#: a que o pacote da interface nova ia precisar), e a direção desta casa é o
#: gerador LER o produto: se `RUMBLE_POLICY_MULT["economia"]` deixar de ser 0,3,
#: a tela, o mockup e o pacote mudam juntos ou nenhum.
#:
#: As leituras por AST de `MULT` e `ORC["SEM_TETO"]` FICAM: elas servem os
#: outros usos deste arquivo (a tabela do orçamento, o `teto_dica`), e são a
#: única forma de ler um número sem importar `structlog`.
fala_do_teto = _aba_conexoes.fala_do_teto

#: O perfil da mesa que esta tela mostra escolhido. É id de BOTÃO do produto, e
#: a tradução para disco é do produto também — a tela não inventa nenhuma das
#: duas pontas.
PERFIL_DA_MESA = ORC["PERFIS"][0]
#: A chave de DISCO daquele perfil — o que `orcamento_em_vigor()` devolveria se
#: ela tivesse declarado este perfil. É o argumento das frases do produto.
ORCAMENTO_DA_MESA = ORC["TETO_POR_PERFIL"][PERFIL_DA_MESA]
TETO_GLOBAL = fala_do_teto(ORCAMENTO_DA_MESA)

# A VÍRGULA TEM UM DONO SÓ — `app/fala_do_mapa.formata_pt_br`, desde 26/08/2026.
# Carregado POR CAMINHO, como o `validar-fala-de-tela.py` o carrega: o módulo é
# zero-dependência de propósito, e passar pelo `__init__` de `app/` traria a GUI.
# O `sys.modules[nome]` ANTES do `exec_module` não é zelo: sem ele o
# `@dataclass` do arquivo estoura, porque `dataclasses` procura o módulo pelo
# nome para resolver as anotações. Mesma sequência do `validar-fala-de-tela.py`.
_alvo = R / "src/hefesto_dualsense4unix/app/fala_do_mapa.py"
_spec = importlib.util.spec_from_file_location("fala_do_mapa_da_tela", _alvo)
_fala = importlib.util.module_from_spec(_spec)
sys.modules["fala_do_mapa_da_tela"] = _fala
_spec.loader.exec_module(_fala)


def num(valor):
    """`1600` → `1.600`; `260.4` → `260,4`; `1106.8` → `1.106,8`.

    A vírgula é do dono único; o ponto de milhar é só a forma desta tela, que
    escreve o teto como `1.600` desde o primeiro desenho.
    """
    inteiro, _, decimal = _fala.formata_pt_br(valor).partition(",")
    milhar = f"{int(inteiro):,}".replace(",", ".")
    return milhar if decimal == "0" and float(valor).is_integer() else f"{milhar},{decimal}"


def palavra_da_ocupacao(fracao):
    """As três palavras do produto — nunca vermelho, rádio cheio tem volta."""
    if fracao < RADIO["CORTE_FOLGADA"]:
        return RADIO["PALAVRA_FOLGADA"]
    return RADIO["PALAVRA_APERTADA"] if fracao < RADIO["CORTE_APERTADA"] else RADIO["PALAVRA_CHEIA"]


# ---------------------------------------------------------------------------
# A MÁSCARA E A BATERIA DE CADA CONTROLE SAEM DA ABA CONTROLES, POR AST.
#
# A linha fechada do acordeão traz o resumo que ela pediu — *máscara ·
# microfone · bateria*. Máscara e bateria são LEITURA nesta aba: a máscara
# passou a ser por controle na aba **Jogar** (decisão dela, 28/08) e a bateria
# é da **Controles**. Escrevê-las aqui criaria a segunda verdade sobre o que o
# jogo vê — o P2 aparece como `Xbox 360` na Controles, e um dia apareceria como
# `DualSense` aqui sem ninguém ver.
#
# POR AST, e não por `import aba02`: importar o gerador de outra aba o EXECUTA,
# e ele reescreve `02-controles.html`. Gerador de aba não é biblioteca.
# ---------------------------------------------------------------------------
def _estado_da_aba_controles(campos):
    arq = pathlib.Path(__file__).resolve().parent / "aba02.py"
    for no in ast.parse(arq.read_text()).body:
        if not (isinstance(no, ast.Assign) and len(no.targets) == 1
                and getattr(no.targets[0], "id", "") == "ESTADO"):
            continue
        fora = {}
        for chave, chamada in zip(no.value.keys, no.value.values):
            kw = {k.arg: k.value for k in getattr(chamada, "keywords", [])}
            if faltam := set(campos) - set(kw):
                raise SystemExit(
                    f"ERRO: o ESTADO da aba02 não tem mais {sorted(faltam)} em "
                    f"{chave.value!r}. A linha fechada desta aba mostra a máscara e a "
                    f"bateria de lá — se elas mudaram de nome, mude aqui também.")
            fora[chave.value] = {c: ast.literal_eval(kw[c]) for c in campos}
        return fora
    raise SystemExit("ERRO: `ESTADO` sumiu de aba02.py — o resumo da linha fechada "
                     "desta aba (máscara · microfone · bateria) sai de lá.")


#: SÓ A BATERIA VEM DA ABA CONTROLES. A MÁSCARA saiu de lá em 28/08 e ganhou
#: fonte única em `monta.MESA[...]["mascara"]` — ela estava em três telas e
#: divergia (a Jogar dizia que o P2 era DualSense e o P3 Xbox 360; a Controles e
#: esta aba diziam o contrário, na mesma sessão). Aqui se lê `c["mascara"]`.
DA_CONTROLES = _estado_da_aba_controles({"bat"})
if faltam := {c["pref"] for c in MESA} - set(DA_CONTROLES):
    raise SystemExit(f"ERRO: a MESA tem {sorted(faltam)} e o ESTADO da aba02 não.")

# ---------------------------------------------------------------------------
# O QUE ESTA ABA GOVERNA EM CADA CONTROLE.
#
# O MICROFONE NASCE LIGADO nos quatro, e isso não é uma coluna por controle: é
# a decisão dela de 25/08 (`audio-e-giro-nascem-ligados-em-todo-jogo`) — mic
# ATIVO, e só muda se ela mudar e salvar.
#
# O TETO é o que varia, e varia de propósito: a tela precisa mostrar as DUAS
# leituras que a decisão de 28/08 exige — quem SEGUE o global e quem SOBREPÕE.
# O P3 é o que sobrepõe porque é o que está com a bateria mais baixa da mesa
# (31%, medido na aba Controles, de onde esta tela lê o número).
# ---------------------------------------------------------------------------
#: Também do produto, e pela mesma razão de `fala_do_teto`: a opção que não
#: grava nada tem um dono só (`gui.aba_conexoes.SEGUE_O_GLOBAL`).
SEGUE_O_GLOBAL = _aba_conexoes.SEGUE_O_GLOBAL
TETO_DO_CONTROLE = {"p3": COM_TETO}
#: O QUE O BOTÃO FÍSICO DO MICROFONE FAZ — e ele deixou de ser ESCOLHA em
#: 04/09/2026. Ver `a08_conexoes.FALA_DO_BOTAO_DO_MIC`, que é o dono das duas
#: falas e o único lugar que traduz o `mic_button_toggles_system` do daemon.
#:
#: A CENA DA BANCADA MOSTRA O PADRÃO DO PRODUTO (`DaemonConfig
#: .mic_button_toggles_system = True`), e não uma das duas escolhida a dedo:
#: o desenho tem de parecer o que a máquina de quem instala vai mostrar.
BOTAO_DO_MIC = _pacote08.FALA_DO_BOTAO_DO_MIC[True]


#: ONDE O TETO GLOBAL MORA AGORA — e não é mais nesta aba.
#:
#: Decisão dela, 28/08: *"Teto da Vibração, que na verdade é Perfil de
#: Bateria"*. O dropdown dos três perfis do produto
#: (`app/actions/config/secao_orcamento.py`) mudou-se para a aba **Sistema**,
#: onde vira **Perfil de Bateria**. O código já lhe dava razão antes do nome:
#: `secao_orcamento.py:127` chama a chave de `PERFIL_BATERIA_LONGA`, e a
#: `D-PERFIL-DE-DESEMPENHO` (24/08) diz com todas as letras que *"o perfil decide
#: o que custa BATERIA"*.
#:
#: O QUE FICA NESTA ABA é a régua de turnos por adaptador — ela mede o RÁDIO, e
#: não a bateria. Esta aba passa a ser LEITORA do global: o campo de cada
#: controle continua podendo sobrepô-lo, e o `?` dele diz em que aba o global se
#: muda. Ponteiro com endereço, que é o que a frase antiga ("abaixo") não tinha.
#:
#: A SEÇÃO CONTINUA CHAMANDO-SE "DESEMPENHO", e a decisão é minha, com o porquê
#: aqui para ela derrubar numa frase. Foi proposto renomeá-la para "Rádio em
#: uso", que é o que ela mostra — e a proposta CAI numa medição de duas
#: palavras: o subtítulo é literal dela (*"o rádio de cada adaptador, em
#: fatias"*), então "Rádio em uso" produziria **"Rádio em uso • O rádio de cada
#: adaptador, em turnos"** — a palavra "rádio" duas vezes em oito, no mesmo
#: rótulo. Trocar o subtítulo para desfazer a repetição seria mexer na frase
#: dela, que não foi o que ela pediu.
#:
#: E "Desempenho" não fica órfão: ele nomeava a régua, e não o dropdown. Com o
#: dropdown fora, a colisão que existia — "perfil de desempenho"
#: (`D-PERFIL-DE-DESEMPENHO`) e "Desempenho" a seção — desaparece em vez de
#: piorar: o perfil agora se chama "Perfil de Bateria" e mora noutra aba, e nesta
#: sobra um sentido só para a palavra. O que a seção mede — quanto do tempo do
#: rádio está em uso — é desempenho, e de nada mais.
#: Os dois nomes MUDARAM-SE PARA O PRODUTO em 01/09/2026 — `gui.aba_conexoes` —,
#: junto com a frase do `?` que os usa. O comentário acima fica: ele é a razão
#: da mudança de aba, e razão não se repete no outro arquivo.
CASA_DO_TETO_GLOBAL = _aba_conexoes.CASA_DO_TETO_GLOBAL
ABA_DO_TETO_GLOBAL = _aba_conexoes.ABA_DO_TETO_GLOBAL

#: A LEITURA "Vale Sem teto, do global, abaixo" SAIU DA TELA — decisão dela,
#: `D-O-SEM-TETO-SAI-DOS-DOIS-LUGARES` (28/08): *"some a leitura, fica o
#: seletor"*. Ela saiu dos DOIS lugares em que estava: destas quatro linhas de
#: controle (y=271 a 384, o que ela via) e da capa do Desempenho (y=834, fora da
#: dobra — o que casava letra por letra com o pedido dela, e que ela não podia
#: ter visto).
#:
#: E o "abaixo" caducou por tabela: com o teto global mudando-se para a aba
#: **Sistema**, o endereço que esta frase dava passou a apontar para um lugar que
#: não existe mais nesta aba. Duas razões independentes para a mesma saída.
#:
#: A frase do que VALE não se perdeu: ela continua no `?` do campo, que é onde
#: ela é lida sob demanda em vez de ocupar uma coluna nas quatro linhas. E lá ela
#: é UMA frase por caso, não três pedaços costurados: costurada, o texto saía
#: *"vale Sem teto, do global, na aba Sistema. O global hoje é Sem teto, e quem o
#: muda é o Perfil de Bateria, na aba Sistema"* — "Sem teto" duas vezes e "na aba
#: Sistema" duas vezes, na mesma dica.
#: O GLOBAL VIVO DA BANCADA — o `state['rumble_policy']` que o daemon publicaria.
#: O desenho mostra a mesa em repouso, e "em repouso" é o padrão que o produto
#: assume quando ninguém escolheu nada (`profiles/manager._RUMBLE_POLICY_PADRAO`).
#: ELE NÃO É O ORÇAMENTO, e a distinção é o defeito inteiro que 01/09/2026
#: corrigiu: o orçamento põe um teto POR CIMA da política viva, e é a viva que
#: multiplica o que chega ao motor.
GLOBAL_VIVO = _constantes(R / "src/hefesto_dualsense4unix/profiles/manager.py",
                          {"_RUMBLE_POLICY_PADRAO"})["_RUMBLE_POLICY_PADRAO"]


def _vibracao_da_bancada(c):
    """As quatro pontas que a BANCADA declara para um controle do desenho."""
    return _aba_conexoes.Vibracao(
        do_controle=TETO_DO_CONTROLE.get(c["pref"]),
        do_perfil=None,
        a_viva=GLOBAL_VIVO,
        orcamento=ORCAMENTO_DA_MESA,
    )


def teto_que_vale(c):
    """(o que a tela mostra no CAMPO, a frase de quem manda neste controle).

    A CONTA É DO PRODUTO desde 01/09/2026 — `gui.aba_conexoes.teto_que_vale`. O
    que sobra aqui é a BANCADA: qual controle sobrepõe (`TETO_DO_CONTROLE`) e
    qual perfil de mesa esta tela mostra escolhido (`PERFIL_DA_MESA`). Na tela
    viva, as quatro pontas vêm do perfil dela, do `state` do daemon e do
    `maquina.json`.
    """
    return _aba_conexoes.teto_que_vale(_vibracao_da_bancada(c))


# ---------------------------------------------------------------------------
# A MESA FÍSICA: os adaptadores, e quem fala em cada um.
#
# `prefs` aponta para a MESA — nunca repete um nome de controle. Assim a pista
# do rádio, a fita do topo e as linhas do acordeão não podem discordar.
#
# MAIÚSCULA EM "Sem nome" E "Interno": eles são VALOR DE CÉLULA, e a célula
# vizinha da mesma coluna já era maiúscula — "Sala" na coluna Nome, "Entrada 3"
# na coluna Onde está. Duas células da mesma coluna com caixa diferente é o que
# faz a tabela parecer montada por duas pessoas. O `SEM_NOME` vira constante
# porque o valor é lido DUAS vezes: uma para escrever a célula e outra para
# decidir se ela sai apagada (`class="mudo"`) — dois literais iguais é um que
# pode ficar para trás.
# O `SEM_NOME` PASSOU A VIR DO PACOTE em 04/09/2026, com a tabela: agora quem
# escreve essa célula na tela viva é `a08_conexoes._html_dos_adaptadores`, e
# duas grafias da mesma palavra é o que faz o desenho e o produto divergirem
# no primeiro dia em que uma delas mudar.
# ---------------------------------------------------------------------------
SEM_NOME = _pacote08.SEM_NOME
ADAPTADORES = [
    {"nome": "Sala", "modelo": "TP-Link UB500", "onde": "Entrada 3",
     "detalhe": "traseira", "prefs": ["p2", "p3"]},
    {"nome": SEM_NOME, "modelo": "Intel AX211", "onde": "Interno",
     "detalhe": "M.2", "prefs": []},
]

#: Os rádios que falam em 2,4 GHz perto do adaptador. É desta lista que sai a
#: contagem da linha NOTA do exame — ela dizia "4" digitado, e divergiria da
#: tabela no primeiro vizinho a mais.
RADIOS_VIZINHOS = [
    ("Intel AX211 (banda 2,4)", "Wi-Fi", False),
    ("Logitech Unifying", "Teclado", False),
    ("2.4G Wireless Rcvr", "— O que é? —", True),
    ("Unknown 0e8d:0608", "— O que é? —", True),
]

#: AS RESPOSTAS DO "— O que é? —", E ELAS NÃO SE DIGITAM MAIS AQUI — 01/09/2026.
#:
#: A lista estava escrita duas vezes: nesta linha e em
#: `gui/aba_conexoes.RESPOSTAS_DO_VIZINHO`, que é a camada de tela DESTA MESMA
#: aba. As duas eram idênticas byte a byte, e é essa a armadilha: enquanto forem
#: iguais ninguém vê problema, e no dia em que uma ganhar uma opção a tela
#: oferece uma resposta que o gesto não sabe traduzir — o `<select>` mostra
#: "Fone", ela escolhe, e o clique **recusa dizendo que não conhece a palavra**.
#:
#: O gesto `vizinho-o-que-e` traduz o rótulo desta lista para o `tipo` do
#: esquema (`secao_mesa._TIPOS_DE_RADIO`); derivar daqui é o que mantém as três
#: listas amarradas num dono só.
VIZINHOS = list(_aba_conexoes.RESPOSTAS_DO_VIZINHO)


#: O ENDEREÇO DA PRIMEIRA `<option>` — a pergunta em si.
#:
#: Ela deixa de ser texto morto em 03/09/2026 porque a tela passou a SUGERIR: o
#: pacote reescreve o TEXTO desta opção com o que o kernel leu daquele rádio,
#: ainda vestido de pergunta (`— Teclado? —`), e ela confirma escolhendo na
#: mesma caixa. Decisão dela, perguntada se a "Câmera" do kernel é a "Webcam" da
#: lista: *"Depende do aparelho. (…) A tela pode SUGERIR e deixar você
#: confirmar, em vez de decidir sozinha."*
#:
#: NÃO NASCE UMA CAIXA NOVA, e isso é o contrato: a `<option>` já existia, o
#: `<select>` já existia, e nem uma nem outro mudam de tamanho, de lugar ou de
#: cor. A janela estável resolve o mesmo problema com TRÊS caixas a mais por
#: linha — a palavra, o selo `(lido)` e um botão "Corrigir"
#: (`secao_mesa._celula_respondida`) —, e essas três são desenho DELA.
PERGUNTA_DO_VIZINHO = ' data-campo="vizinho-pergunta"'


def viz_sel(escolhida):
    return "".join(
        f'<option{" selected" if v == escolhida else ""}'
        f'{PERGUNTA_DO_VIZINHO if i == 0 else ""}>{v}</option>'
        for i, v in enumerate(VIZINHOS))


def sel(opcoes, escolhida, classe="pronto", dica="", gesto="", campo=""):
    """Um `<select>` com a opção escolhida marcada — uma forma só na tela.

    `gesto` é o ENDEREÇO do que este campo faz, e ele entra mesmo quando ninguém
    o atende ainda: o piloto único (`hefesto_vivo.py`) imprime
    `[gesto sem dono] 08-conexoes.html · <nome>` e o clique vira inventário do
    que falta, em vez de sumir sem uma linha. Sem o atributo, o `closest()` do
    ouvinte não acha nada e o clique não produz **nem recusa** — que é a forma
    calada do mesmo defeito.

    `campo` é o endereço da PINTURA, e ele vem com `data-hef-alvo="valor"` de
    propósito: sem o alvo, o piloto escreveria o texto DENTRO do `<select>` em
    vez de escolher a opção (`hefesto_vivo.BOOTSTRAP`, `escrever()`), e a lista
    ganharia uma linha solta "Ligado" no meio das opções. Um campo com gesto e
    sem pintura é pior que os dois faltando: o clique grava e a tela continua
    mostrando o padrão do desenho, então o segundo clique parece o primeiro.
    """
    marca = f' data-gesto="{gesto}"' if gesto else ""
    endereco = f' data-campo="{campo}" data-hef-alvo="valor"' if campo else ""
    corpo = "".join(f'<option{" selected" if o == escolhida else ""}>{o}</option>'
                    for o in opcoes)
    return f'<select class="{classe}" title="{dica}"{marca}{endereco}>{corpo}</select>'


# ---------------------------------------------------------------------------
# O QUE A MESA RESPONDE — tudo o que a tela conta, contado aqui.
#
# QUANTOS CARDS: quantos estiverem ligados, e só eles (decisão dela, 28/08).
#
# O CAMPO PASSOU A EXISTIR — 31/08/2026. Este comentário dizia *"um filtro por um
# campo 'ligado' que não existe seria inventar estado"*, e estava certo até o dia
# em que ela mandou deixar dois lugares vazios na mesa: nasceu `conectado` em
# `monta.MESA`, e com ele a lista `CONECTADOS`.
#
# ENQUANTO ISSO NÃO FOI FEITO, A ABA CONTAVA QUATRO EM SILÊNCIO: o Check-up dizia
# *"as entradas dão energia para os 2 controles no cabo"* contando o P4, que não
# está na mesa, e *"2 dos seus 4 controles falam nessa mesma faixa"* contando o
# P3. Nenhuma régua viu — as frases estavam gramaticalmente perfeitas e os
# números batiam com a lista errada.
#
# `MESA` continua sendo quem o DESENHO percorre: é ela que dá os quatro lugares,
# e é o lugar vazio que ensina que ali cabe um e ele não está.
# ---------------------------------------------------------------------------
NO_CABO = [c for c in CONECTADOS if c["via"] == "USB"]
NO_RADIO = [c for c in CONECTADOS if c["via"] == "BT"]
POR_PREF = {c["pref"]: c for c in MESA}

#: O ENDEREÇO DA ORDEM DE SERVIÇO — 03/09/2026, `MIGRA-08-01`, e ele mata a
#: mentira mais cara desta aba.
#:
#: O que a coluna da direita do Check-up desenha é uma ORDEM DE SERVIÇO — uma
#: instrução para ela mexer no gabinete: *"Mova o adaptador Bluetooth da Entrada
#: 3 para a Entrada 9"*, com de→para, ganho e um `?` de duas frases. Tudo
#: escrito à mão neste arquivo, tudo apresentado como diagnóstico da máquina
#: dela. Fotografado no produto vivo em 03/09, com o exame dizendo CERTO nas
#: três linhas que corriam.
#:
#: O DONO DO CARD JÁ EXISTIA: `gui.aba_conexoes.html_da_ordem`, com estas MESMAS
#: classes — foi deste desenho que ele foi extraído. O que faltava era o produto
#: chamá-lo; ver `pacotes.a08_conexoes._html_da_ordem`.
#:
#: O ALVO É `html` porque o card muda de FORMA: sem ordem pendente ele é uma
#: linha só (*"Nenhuma mudança recomendada agora."*, texto do dono), e com ordem
#: são quatro blocos. Não há endereço para um filho que ainda não existe — é a
#: mesma razão da fita e do mapa do gabinete.
#:
#: O NOME É CONSTANTE PORQUE O PACOTE O EMITE COM ESTA GRAFIA. Um endereço
#: escrito duas vezes é um endereço que diverge sem sintoma: o `achar()` não o
#: encontra e escreve zero, calado.
CAMPO_DA_ORDEM = "ordem"

#: A CONTAGEM DA SEÇÃO GESTÃO DE CONTROLES, e ela tem UM dono: o
#: `gui.aba_conexoes.texto_da_contagem`, que escreve *"2 na mesa • 1 no cabo • 1
#: no rádio"* — a frase inteira, com os três números. Este arquivo a digitava,
#: e era a segunda grafia: com um controle só na mesa, o produto continuava
#: mostrando 2/1/1 porque o `<span>` não tinha endereço nem dono.
#:
#: O `Controle` DA BANCADA É MONTADO AQUI porque o dono conta por
#: `Controle.pelo_radio`, e ele lê `via` em MINÚSCULA (`"usb"`/`"bt"`); a mesa
#: do desenho guarda `"USB"`/`"BT"`, que é o que o chip da fita mostra. O
#: `.lower()` é a tradução, e ela fica visível de propósito: sem ele os dois
#: controles do desenho contariam como dois no rádio, calados.
CONTA_DA_GESTAO = _pacote08.html_da_conta(_aba_conexoes.texto_da_contagem([
    _aba_conexoes.Controle(uniq=str(c["pref"]), jogador=int(c["jogador"]),
                           via=str(c["via"]).lower(), bateria=None)
    for c in CONECTADOS]))

#: O microfone segue o TRANSPORTE — ponto final dela, 28/08: *"se tiver em modo
#: rádio, então o mic é modo rádio"*. Não há chavinha e não há heurística de
#: orçamento: os turnos do rádio viraram CONSEQUÊNCIA, e a consequência aparece
#: na régua do Desempenho.
def tem_mic_pelo_radio(c):
    return c["via"] == "BT"


#: O caminho por onde o microfone deste controle chega — DERIVADO, nunca
#: escolhido. Pelo CABO o DualSense expõe placa USB Audio própria e o PipeWire a
#: publica sozinho (medido em 15/08/2026, duas placas ALSA com ~475.000 amostras
#: não-zero). Pelo RÁDIO não existe placa nenhuma — o aparelho não implementa
#: A2DP/HFP/HSP —, e o áudio vem em Opus dentro do HID 0x31: quem o traz é a
#: ponte do Hefesto, que publica um source virtual do PipeWire
#: (`hefesto_dualsense_bt_<nó>`, medido RUNNING em 16/08/2026).
#:
#: MAIÚSCULA DEPOIS DO `•`: o ponto separa CAMPOS nesta casa — é a mesma
#: pontuação do rótulo do controle ("Sony • Player 1 • Cosmic Red • USB"), e ali
#: todo campo começa com maiúscula. "pela ponte" e "placa do controle" eram os
#: dois únicos campos minúsculos da linha fechada, ao lado de "Vê como
#: DualSense" e "Bateria 100%". Medido em 28/08 nas quatro linhas.
#: O DONO DAS DUAS FRASES MUDOU-SE PARA O PACOTE — 03/09/2026, mesmo molde do
#: `rotulo_do_controle` e do `html_da_conta`. Enquanto elas moravam só aqui, o
#: produto não tinha como reescrevê-las: a linha fechada dizia "pelo cabo •
#: Placa do controle" no primeiro lugar e "pelo rádio • Pela ponte" no segundo
#: porque foi assim que a CENA foi desenhada, e não porque o daemon tenha dito.
#: Agora há um dono só, chamado pelos dois — este gerador com a mesa da bancada,
#: o pacote a cada tique com o transporte vivo.
def caminho_do_mic(c):
    return _pacote08.caminho_do_microfone(c["via"])


def custo(c):
    return CUSTO_COM_MIC if tem_mic_pelo_radio(c) else CUSTO_SEM_MIC


# O RÓTULO E A TINTA MUDARAM-SE PARA O PACOTE — 03/09/2026,
# `IDENTIDADE-VEM-DE-CIMA-01`. Eles nomeiam o PLÁSTICO do controle, e o plástico
# é identidade de aparelho: escrito só aqui, o produto não tinha como reescrevê-lo
# e a Gestão de Controles mostrava o `Cosmic Red` do desenho com o White dela no
# cabo. Agora há um dono só, e ele é chamado pelos dois — este gerador com a mesa
# da bancada, o pacote a cada tique com a mesa viva. Mesmo molde da
# `a04_iluminacao.um_botao_de_player`.
rotulo = _pacote08.rotulo_do_controle
tinta_legivel = _pacote08.tinta_legivel


CSS = CSS_GLIFO + CSS_POPUP + """
  /* 6.1 · O RESPIRO DO RÓTULO QUE EXPANDE — 31/08/2026, pedido dela com duas
     fotos desta aba: *"o nome dos campos que expandem não tem respiro"*.

     MEDIDO no Chrome antes de mexer, e a medida acha a causa exata: o
     `.quadro-topo` do esqueleto é `padding:11px 14px 0` — **zero embaixo**. Num
     quadro comum isso não aparece, porque o conteúdo vem logo abaixo e traz o
     próprio respiro. Num acordeão FECHADO não vem nada: sobrava **1px** entre o
     texto e a borda de baixo da faixa, contra 12px em cima. O rótulo não estava
     centrado na faixa — estava encostado nela.

     A CURA DEFINITIVA É UMA VARIÁVEL NO `topo.html`, como a lista dela manda —
     e o `topo.html` está CONGELADO por decisão dela de hoje, enquanto duas
     sessões trabalham na mesma árvore. Esta regra é local à Conexões, que é a
     única aba com acordeão de verdade (medido: `input.abre` = 3 aqui, 0 nas
     outras doze páginas). Quando o esqueleto descongelar, ela sobe para lá e
     esta some. */
  .quadro:has(> input.abre) .quadro-topo{padding-bottom:11px}

  /* O GLIFO DE IGNORAR, um por linha do exame. Ele mora na ponta direita, depois
     do `?`, e nasce apagado: é gesto de recusa, não de ação principal — aceso
     como o `?` ele competiria com o selo, que é quem diz o que a linha achou. */
  .exame .ignora{flex:0 0 17px;width:17px;height:17px;border-radius:50%;padding:0;
    border:1px solid var(--linha);background:none;color:var(--texto-mudo);
    font-size:11px;line-height:1;cursor:pointer}
  .exame .ignora:hover{border-color:var(--orange);color:var(--orange)}

  /* A DICA DAS LINHAS DO EXAME ABRE PARA A ESQUERDA — 31/08/2026, pedido dela:
     *"jogar o tooltip pra alinhar a esquerda"*. A `.dica` do esqueleto nasce em
     `left:22px`, crescendo para a DIREITA a partir do `?`. Aqui o `?` fica na
     ponta direita da linha, a 30px da borda do quadro: 330px de dica crescendo
     para lá saem da janela. Ancorada pela direita, ela cresce para dentro. */
  .exame .ajuda .dica{left:auto;right:22px}

  /* O NOME DO ADAPTADOR É EDITÁVEL NO LUGAR — o botão `Renomear` saiu.
     `contenteditable` é o que o mockup faz sem JavaScript; o DUPLO clique que ela
     pediu é gesto do produto. O tracejado é o que diz que ali se escreve — sem
     ele o campo mente por omissão, parecendo texto morto. */
  .renomeia{border-bottom:1px dashed var(--linha);cursor:text}
  .renomeia:hover{border-bottom-color:var(--cyan)}
  .renomeia:focus{outline:none;border-bottom-style:solid;border-bottom-color:var(--cyan)}

  /* O LUGAR SEM CONTROLE na Gestão. A cor é a do `.vazio` da Gatilhos, que é a
     página que ela mandou copiar; o contraste está medido na prova de tela. A
     borda do plástico não vem — ela identifica a peça que está ali, e não há
     peça a identificar. */
  .gc-item.fora .gc-nome{color:var(--comment)}
  .gc-item.fora{cursor:default}

  /* ================= Conexões =================
     Três assuntos, três quadros, agrupados por PERGUNTA:
       1. "está tudo certo?"   — DUAS colunas: o que eu vi · o que fazer. A
          terceira ("o que só você sabe") saiu em 28/08: as duas perguntas de
          rádio passaram a morar no "Mapear Entradas", que é a janela onde
          ela já declara a sala.
       2. "Gestão de Controles"   — os controles ligados, em acordeão: o da fita
          aberto, os outros na linha fechada com o resumo.
       3. "Rádio e adaptadores"— o inventário físico da mesa, e o Desempenho
          embaixo, separado, porque os turnos são POR ADAPTADOR.
     ------------------------------------------------------------------ */
  /* o "?" ao lado de um rótulo só vira bolinha se a linha for flex — solto num
     bloco ele herda `inline` e a largura/altura de 17px não valem nada */
  .linha-rot{display:flex;align-items:center;gap:8px;height:19px;margin-bottom:4px}
  /* DUAS colunas com a mesma gramática da Navegação e da Gatilhos — o nome é o
     mesmo de propósito: é a régua que confere a soma das colunas. */
  .duas-colunas{display:grid;grid-template-columns:1fr 1fr;gap:0;align-items:stretch}
  /* 17 e não 16: a barra de 1 px é `border-left` da coluna da direita e sai da
     LARGURA dela. Com 16 dos dois lados os dois botões do inventário mediam
     547,5 e 546,5 — a diferença que ela repara. O pixel volta aqui. */
  .duas-colunas > .lado-e{padding-right:17px}
  .lado-e,.lado-d{display:flex;flex-direction:column;min-width:0}
  .lado-d{padding-left:16px;border-left:1px solid var(--border-sutil)}
  .pilha{display:flex;flex-direction:column;gap:8px}

  /* AS DUAS FILEIRAS DE BOTÕES VIRARAM UMA SÓ, com os quatro, e ela mora FORA
     das colunas — ordem escrita por ela em 28/08: *"Examinar de novo. / Já Movi
     - Reexaminar. / Ignorar / Ver Ordens ignoradas."* Com um botão em cada
     coluna nenhum arranjo dá essa ordem: a leitura de uma grade de duas colunas
     é esquerda→direita, linha a linha, e "Ignorar" (que estava na direita) teria
     de vir antes de "Ver as ordens ignoradas" (que estava na esquerda).
     E NÃO CUSTA ALTURA: as duas fileiras já caíam na mesma linha por construção,
     então juntá-las devolve os mesmos px — medido, 205 antes e 205 depois.
     O que sobrou nas colunas é só o que reparte a SOBRA de altura entre os itens
     de cada uma, para as duas terminarem juntas sem `space-between`. */
  .col-exame{flex:1;display:flex;flex-direction:column}
  .col-exame .exame{flex:1 0 auto}
  .lado-d .col-ordem{flex:1;display:flex;flex-direction:column}
  .lado-d .col-ordem > .ordem{flex:1;display:flex;flex-direction:column}
  /* 11px, e o número é MEDIDO, não escolhido: com os botões dentro das colunas o
     vão nascia da sobra que os itens de cada coluna repartiam entre si, e não de
     uma margem. 11 é o que devolve o quadro aos mesmos 204px e a fileira ao mesmo
     y=575 de antes — com 12 o quadro ia a 205. */
  .acoes.quatro{margin-top:11px}
  /* e a sobra de altura do card é repartida entre as TRÊS linhas dele, como as
     cinco linhas do exame repartem a da esquerda — nunca um buraco no meio */
  .ordem .faca,.ordem .receita,.ordem .ganho{flex:1 0 auto}

  /* ---- o exame: selo, fato, e o "por que importa" no ? ----
     O selo é o MESMO da aba Lançadores, que ela aprovou (CHEGA / NÃO CHEGA / NÃO
     ACHEI): 10px, mono, fundo cheio. As palavras vieram para o português —
     "WARN" e "INFO" eram as duas únicas palavras em inglês da tela. */
  .exame{display:flex;align-items:center;gap:9px;min-height:20px;font-size:12px;
         color:var(--texto-suave)}
  .exame .selo{flex:0 0 62px;text-align:center;font-size:10px;font-weight:600;
               padding:2px 0;border-radius:4px;font-family:'JetBrains Mono',monospace}
  .selo.ok{background:var(--green);color:var(--app-bg)}
  .selo.warn{background:var(--orange);color:var(--app-bg)}
  .selo.info{background:var(--comment);color:var(--app-bg)}
  /* AS TRÊS DE CIMA VIRARAM RESERVA — 03/09/2026. Elas continuam cravadas na
     pílula porque é o que o desenho ABERTO NO NAVEGADOR mostra (o mockup é
     HTML estático e ninguém o pinta), e porque uma linha do exame que o
     produto não preencheu tem de continuar parecendo o que ela parecia.

     QUEM MANDA QUANDO O PRODUTO FALA são as três regras abaixo. O interruptor
     é um `<i class="est">` invisível por estado, irmão da pílula, com
     `data-campo` próprio (`a08_conexoes.ENDERECO_DO_ESTADO`) — e o combinador
     `~` é o que deixa a cor do IRMÃO chegar à pílula sem que a pílula precise
     de um segundo `data-campo`, que o vocabulário não permite.

     POR QUE NÃO NA PRÓPRIA PÍLULA: o alvo `classe` acende UMA classe por
     elemento. Com um endereço só, a pílula sabia dizer `problema` e mais nada
     — e com os três achados `certo` da mesa dela a segunda linha mostrava a
     palavra CERTO dentro da pílula LARANJA, que é a cor que o mockup cravou
     naquela posição. A palavra era do produto; a cor, do desenho.

     A ESPECIFICIDADE É O CONTRATO: `.exame .est-ok.on ~ .selo` tem quatro
     classes e vence `.selo.ok`, que tem duas. */
  .exame .est{display:none}
  .exame .est-ok.on ~ .selo{background:var(--green);color:var(--app-bg)}
  .exame .est-warn.on ~ .selo{background:var(--orange);color:var(--app-bg)}
  .exame .est-info.on ~ .selo{background:var(--comment);color:var(--app-bg)}
  /* O QUARTO SELO — decisão dela, 02/09/2026: *"o que está quebrado agora não
     pode parecer igual ao que só podia estar melhor"*. O `Item` do exame tem
     QUATRO estados (`certo`, `atencao`, `problema`, `nao_sei`) e esta tela  (noqa-acento: chaves de máquina)
     tinha TRÊS cores: `atencao` e `problema` dividiam a pílula laranja.  (noqa-acento: idem)

     A COR É A DA CASA, e não uma nova: `--red` (#ff5555) é o token do que está
     quebrado — é ele que o `.btn.vermelho` do `topo.html` usa. A gramática é a
     mesma das três de cima: fundo cheio no token, texto no `--app-bg`.

     ELA VEM DEPOIS DAS OUTRAS TRÊS DE PROPÓSITO. A pílula nasce no HTML com a
     classe do desenho (`ok`/`warn`/`info`) e o produto ACRESCENTA `grave`
     quando o estado é `problema` — as duas classes convivem no elemento, e com
     a mesma especificidade quem vem por último manda. Trocar a ordem devolveria
     a pílula laranja sem uma linha de diferença no resto.

     A PALAVRA AINDA É "AJUSTAR", e isso é espera DELA: `SELO_DO_ESTADO`
     (`gui/aba_conexoes.py`) manda os dois estados para a mesma palavra, e o
     texto do quarto selo ela ainda não disse. Esta leva entrega a cor. */
  .selo.grave{background:var(--red);color:var(--app-bg)}
  /* O VERMELHO CONTINUA MANDANDO, e a regra abaixo é o que garante isso quando
     um dos interruptores de estado estiver aceso. Ela não deveria correr nunca
     — um achado tem UM estado, e o pacote emite o vazio nos outros três
     endereços —, mas sem ela um instante com dois acesos deixaria o que está
     QUEBRADO com a cor do que só podia estar melhor, que é exatamente a
     confusão que ela mandou desfazer em 02/09. Cinco classes: vence as
     quatro das regras de cima. */
  .exame .est.on ~ .selo.grave{background:var(--red);color:var(--app-bg)}
  /* O `?` ENCOSTA NO TEXTO E SÓ O IGNORAR FICA ISOLADO — 01/09/2026, decisão
     dela: *"tem que alinhar as tooltip pra ficar do lado esquerdo encostando nas
     palavras e só deixar o ignorar isolado."*

     O `.txt` era `flex:1` e comia todo o espaço da linha, empurrando os DOIS
     ícones para a borda direita. Ali eles liam como um par, e não são: o `?`
     explica AQUELA frase — ele pertence a ela — e o `⊘` é uma ação sobre a
     linha inteira. Colados, o ponteiro passa por um para chegar ao outro.

     Agora o texto ocupa o que precisa, o `?` vem logo depois dele, e o
     `margin-left:auto` do ignorar é o que abre o vão até a borda: uma regra, e o
     espaço vazio passa a separar em vez de agrupar. */
  .exame .txt{flex:0 1 auto;min-width:0}
  .exame .ignora{margin-left:auto}

  /* ---- A LINHA DE VEREDITO — decisão D-16 dela, 04/09/2026 ----
     *"Uma linha de veredito no topo."*, *"Na cor do pior achado."*

     O QUE ELA CURA, e a queixa é dela: o Check-up tinha cinco pílulas e nenhum
     veredito. Para saber se está tudo certo era preciso ler as cinco e achar a
     pior — e a segunda ordem de serviço desta bancada, que não cabe nas cinco,
     não entrava nessa leitura de jeito nenhum. A janela estável responde em uma
     linha desde sempre, e o carimbo do lado só diz QUANDO.

     ELA MORA NO TOPO DA SEÇÃO e não dentro da coluna do exame: "no topo" é a
     palavra dela, e a resposta que vale para as duas colunas — o exame à
     esquerda e a ordem de serviço à direita — não pode ficar pendurada em uma
     delas. São 11px de altura mais o vão, e é o preço declarado da decisão.

     A COR VEM POR INTERRUPTOR, um por estado, exatamente como as cinco linhas
     ganharam em 03/09: o alvo `classe` do piloto acende UMA classe por
     elemento, então um nó só não tem como escolher entre quatro cores. Aqui os
     QUATRO são interruptores — inclusive o `problema` —, porque não há pílula
     com classe cravada a reaproveitar: a linha inteira nasce do produto.

     O `~` LEVA A COR DO IRMÃO ao ponto e ao texto sem que nenhum dos dois
     precise de um segundo `data-campo`, que o vocabulário de endereço não
     permite. É o mesmo combinador de `.exame .est-ok.on ~ .selo`.

     O ESTADO DE REPOUSO É O CINZA DE "não sei", e não o verde: enquanto o
     produto não respondeu, a linha não pode afirmar que está tudo bem — é o F7
     desta casa, o estado em que o produto não sabe se disfarçando do estado em
     que está tudo certo. */
  .veredito{display:flex;align-items:center;gap:9px;min-height:19px;font-size:12px;
            font-weight:600;color:var(--texto-suave);margin-bottom:11px}
  .veredito .vst{display:none}
  .veredito .ponto{flex:0 0 8px;width:8px;height:8px;border-radius:50%;
                   background:var(--comment)}
  .veredito .vst-ok.on ~ .ponto{background:var(--green)}
  .veredito .vst-warn.on ~ .ponto{background:var(--orange)}
  .veredito .vst-info.on ~ .ponto{background:var(--comment)}
  .veredito .vst-bad.on ~ .ponto{background:var(--red)}
  .veredito .vst-ok.on ~ .txt{color:var(--green)}
  .veredito .vst-warn.on ~ .txt{color:var(--orange)}
  .veredito .vst-info.on ~ .txt{color:var(--texto-suave)}
  /* O VERMELHO POR ÚLTIMO, e pela mesma razão do `.selo.grave`: um instante com
     dois interruptores acesos não pode deixar o que está QUEBRADO com a cor do
     que só podia estar melhor. */
  .veredito .vst-bad.on ~ .txt{color:var(--red)}

  /* ---- a ordem de serviço: imperativo, receita e ganho ---- */
  .ordem{border:1px solid var(--border-forte);border-radius:7px;background:var(--app-bg);
         padding:10px 12px}
  .ordem .faca{display:flex;align-items:center;gap:8px;
               font-size:12.5px;color:var(--fg);font-weight:600;line-height:1.35}
  .ordem .receita{display:flex;align-items:center;gap:8px;margin-top:8px;flex-wrap:wrap}
  .ordem .caixa{border:1px solid var(--border-forte);border-radius:5px;padding:3px 9px;
                font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--texto-mudo);
                background:var(--panel)}
  .ordem .caixa.alvo{border-color:var(--green);color:var(--green)}
  /* BLOCO, não flex: em flex o espaço entre o rótulo e o texto é colapsado e saía
     "Ganho esperado:saí do controlador" */
  .ordem .ganho{margin-top:8px;font-size:11.5px;color:var(--green)}
  .ordem .ganho span{color:var(--texto-mudo)}

  /* ---- botões: todo grupo divide a largura do bloco em partes IGUAIS ----
     A régua dela é estrita: 273/273/273/273 na Jogar, 260 nos 38 da Gatilhos,
     145×4 na Vibração, 173×6 na Perfis. Aqui eram 134/159, 157/71 e 170/192. */
  .miolo .acoes{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:8px;width:100%}
  .miolo .acoes .btn{width:100%;display:flex;align-items:center;justify-content:center;
                     padding:0 10px}

  select.pronto{border-radius:6px;font-size:11.5px;font-family:inherit;padding:0 8px;
    border:1px solid var(--border-forte);background:var(--app-bg);color:var(--texto-suave);
    cursor:pointer}
  select.pronto:hover{border-color:var(--comment)}
  /* o dropdown que ainda espera resposta chama o olho pela borda, não por faixa */
  select.pronto.pergunta{border-color:var(--cyan);color:var(--cyan)}

  /* ================= o acordeão da Gestão de Controles =================
     CSS PURO, ZERO JAVASCRIPT — o mockup inteiro não tem uma linha de script, e
     o cruzamento do mapa do controle já é feito só com `:has()`. Aqui a peça é
     um grupo de `<input type=radio>` escondido: cada linha fechada é um
     `<label>` que o marca, e por ser RÁDIO marcar um desmarca os outros — que é,
     ao pé da letra, *"clicar num abre e fecha os outros"*.

     A CLASSE NÃO PODE SE CHAMAR `peca` NEM `tira` NEM `mesa`, e as três
     cicatrizes são medidas: `class="peca"` aparece 39 vezes DENTRO do
     `ds_limpo.svg`; `.tira` é a fila de abas do esqueleto (a aba Controles
     pagou 8px de cabeçalho por isso); `.mesa` já existe no `topo.html`. Nome de
     classe se confere no `topo.html` E no SVG, ANTES de escrever. */
  .gc-r{display:none}
  /* UMA LISTA EMOLDURADA, E NÃO QUATRO CARTÕES SOLTOS — e o preço estava medido.
     Quatro cartões com borda de 2px e 9px de vão entre eles custavam 4×4 de
     borda + 27 de vão = **43px** que não mostram nada: mais do que uma linha
     inteira de controle (34). Com uma moldura só e fios de 1px entre as linhas
     o mesmo conteúdo cabe em 125px fechado, contra 163 — e foram esses 44px que
     puseram o terceiro quadro de volta na tela.
     A COR LIDA NÃO SE PERDEU: ela virou a barra de 3px na aresta esquerda de
     cada linha, que é a MESMA promessa da borda inteira e agora cai numa coluna
     só, alinhada nas quatro — que é mais fácil de comparar do que quatro
     retângulos de cores diferentes. */
  .gc{display:flex;flex-direction:column;border:1px solid var(--border-forte);
      border-radius:9px;background:var(--app-bg);overflow:hidden}
  /* A BORDA É A COR QUE O HEFESTO LEU DO APARELHO — e só isso.
     Decisão dela, 28/08: sem seletor de cor nesta aba; quem o produto lê,
     mostra; quem ele não lê fica com borda NEUTRA, e está dito. Pelo cabo ele
     pergunta e o valor vem de lá; pelo rádio ele AINDA NÃO PERGUNTA
     (`ONDA-CONEXOES-11`) — e uma borda colorida ali seria uma cor que ninguém
     leu.

     A COR VIROU ELEMENTO — 03/09/2026, `IDENTIDADE-VEM-DE-CIMA-01`. Ela era um
     `--plastico:#hex` INLINE no `.gc-item`, e um `#hex` inline é o mockup
     mandando na tela: com o controle White dela no cabo, a linha continuava com
     a borda do Cosmic Red do desenho. O `escrever()` do piloto **não tem alvo de
     variável de CSS** — não há como um pacote escrever um `--plastico`. Então a
     cor lida passa a ser a tinta de um elemento, sobreposta aos mesmos 3px da
     borda: o desenho não muda um pixel e o pacote passa a pintá-la.

     O ALVO É `cor` E NÃO `fundo`, e a diferença é MEDIDA, não de gosto: o
     `fundo` compara antes de escrever, e o CSSOM normaliza na atribuição
     (`#ae335a` volta `rgb(174, 51, 90)`). Um hex por ali nunca volta igual ao
     que se escreveu e soma UMA pintura por tique, para sempre — o contador de
     pinturas é O instrumento com que esta casa prova que um endereço existe, e
     um contador que infla é pior que um campo parado. O alvo `cor` escreve e
     SÓ ENTÃO compara, exatamente por causa disso. Daí o `background:currentColor`.

     VAZIO NÃO INVENTA: sem cor lida o pacote manda vazio, o alvo `cor` devolve
     o elemento à folha de estilo (`color:transparent`) e a borda neutra
     reaparece — regra dela, campo sem informação não mostra nada. */
  .gc-item{position:relative;
           border-left:3px solid var(--border-forte);
           border-top:1px solid var(--border-sutil)}
  .gc-item:first-child{border-top:none}
  /* `left:-3px` é medido do lado de DENTRO da borda (o bloco que contém um
     absoluto é a caixa de padding), logo a tinta cai exatamente sobre os 3px da
     borda esquerda. `top:-1px` cobre também a linha de 1px que separa uma linha
     da outra — sem ele a barra nasceria 1px abaixo em todas menos a primeira. */
  .gc-cor{position:absolute;left:-3px;top:-1px;bottom:0;width:3px;display:block;
          color:transparent;background:currentColor}
  .gc-cabeca{display:flex;align-items:center;gap:11px;
             height:30px;padding:0 12px;font-size:12px;color:var(--texto-mudo)}
  /* O ALVO DO CLIQUE ENVOLVE O TEXTO, e não o cobre. Uma capa `position:absolute`
     por cima da linha inteira resolvia o clique e MATAVA o `title` de cada
     pedaço: quem passasse o mouse sobre "vê como Xbox 360" via a dica da capa,
     não a do campo. Com o `<label>` ENVOLVENDO os spans, o clique continua
     valendo em toda a linha e a dica de dentro é a que aparece.
     E o gesto de FECHAR mora na seta, que é um segundo `<label>` — o `for` de um
     label não muda com CSS, e `<label>` dentro de `<label>` é HTML inválido. */
  .gc-abre{flex:1;min-width:0;height:100%;display:flex;align-items:center;gap:11px;
           cursor:pointer;border-radius:7px}
  .gc-abre:hover,.gc-seta:hover{background:rgba(255,255,255,.035)}
  /* O NOME TEM UMA LARGURA SÓ NAS QUATRO LINHAS, e isso não é capricho: com ele
     natural, os quatro rótulos mediam 200,4 / 206,2 / 214,3 / 168,9 px, e o vão
     entre o nome e o resumo mudava 45px de uma linha para a outra — ela repara
     em dois. Com a coluna fixa o vão é o mesmo nas quatro, e o resumo continua
     encostado à direita. O teto é o rótulo mais largo da mesa (o P3, "Galactic
     Purple"); a folga é a diferença para ele. */
  .gc-nome{color:var(--fg);font-weight:600;white-space:nowrap;flex:0 0 var(--larg-nome)}
  /* GRADE, e não uma fila: as colunas do resumo — máscara, microfone e bateria —
     têm de começar no MESMO x nas linhas todas. Em fila cada uma começava onde o
     nome do controle acabava, e são nomes de comprimentos diferentes: o olho
     compara colunas que não existem.
     AS FRAÇÕES SÃO AS LARGURAS NATURAIS MEDIDAS (126 / 272 / 76 px, o conteúdo
     mais largo de cada coluna nas quatro linhas), e não três números escolhidos:
     em `fr` elas repartem a linha inteira na mesma proporção, o que apaga o vão
     de 350px que sobrava entre o nome e um resumo encostado à direita. Como as
     linhas têm todas a mesma largura, as colunas caem no mesmo x sozinhas.
     A última é `justify-self:end` para os percentuais terminarem juntos, colados
     na seta — número que se compara se lê pela direita. */
  .gc-resumo{flex:1;display:grid;grid-template-columns:126fr 272fr 76fr;
             gap:10px;align-items:center;font-size:11.5px;color:var(--texto-mudo);
             white-space:nowrap}
  .gc-resumo > :last-child{justify-self:end}
  .gc-resumo b{color:var(--texto-suave);font-weight:500}
  /* 42px E NÃO 16, e a largura é a MESMA nos três estados de propósito: no
     estado "Todos" o gesto não é uma seta, é a palavra `só este` — e uma coluna
     que muda de largura quando a pessoa clica desloca os percentuais de bateria
     das quatro linhas de uma vez. Largura fixa, conteúdo variável. */
  .gc-seta{flex:0 0 42px;height:100%;display:flex;align-items:center;justify-content:center;
           color:var(--comment);font-size:9px;cursor:pointer;border-radius:5px}
  /* O MENOR DEFEITO DA MEDIÇÃO, e ele era de SENTIDO: no estado "Todos" as
     quatro linhas mostravam `▾` com a dica *"Abre este controle"* — quatro setas
     de abrir sobre quatro linhas já abertas. Ali o gesto é outro (estreitar para
     um), e por isso ganha palavra em vez de seta. A dica do corpo da linha
     também mudou: ela agora vale nos dois estados, porque `title` não muda com
     CSS — "deixa só este aberto, os outros fecham" é verdade tanto quando esta
     linha está fechada quanto quando as quatro estão abertas. */
  .gc-seta.so{font-size:10px;letter-spacing:.2px}
  .gc-seta.fecha,.gc-seta.so{display:none}
  /* O CORPO NASCE FECHADO — e fecha por ALTURA ZERO, não por `display:none`.
     A razão é medida: a régua mede TODO `<select>` e TODO `<button>` do miolo e
     exige que cada família tenha uma altura só. Com `display:none` os campos dos
     três controles fechados medem **0**, e ela reprova a aba inteira —
     `altura divergente em select.pronto: 36 / 0`. Com `height:0;overflow:hidden`
     o navegador continua dando ao campo os 36px do token e simplesmente não o
     pinta: a régua mede o que o desenho promete, e o olho não vê nada.
     `box-sizing:border-box` do esqueleto faz os 40 do aberto já incluírem os
     2+2 de padding — 36 de campo, que é o `--h-escolha`. Foram 48 até 28/08: os
     8px vieram do padding, e não do campo, porque a linha fechada logo acima já
     dá ar ao campo — e no estado "Todos" eles são multiplicados por quatro. */
  .gc-corpo{display:flex;align-items:center;gap:8px;padding:0 12px;
            height:0;overflow:hidden}
  /* 48px e não 58: nesta largura o desenho mede 33,1px de altura e cabe DENTRO
     da linha de 36 do campo, sem crescer o corpo da linha. A proporção é a do
     `viewBox` (116,684 × 80,472), e não uma altura digitada.

     ESTE DESENHO SEGUE O APARELHO desde 03/09/2026 — ver `desenho_do_controle`,
     que é quem lhe dá o endereço. A cor dele viaja num ATRIBUTO
     (`data-colorway` do `<svg>`), e o alvo `atributo` do piloto é quem o
     escreve: vinte bytes por tique.

     A ROTA ÓBVIA FOI TENTADA E REPROVOU NA MEDIÇÃO, e é por isso que o alvo não
     é `html`: envolver o `<svg>` num `data-campo` com alvo `html` e o pacote
     emitir o desenho na cor lida custa, com os dois controles dela, 31 tiques:

         sem o desenho    2 pinturas / 31 tiques    tique mediano  4,24 ms
         com o desenho   31 pinturas / 31 tiques    tique mediano 13,56 ms

     Uma pintura POR TIQUE, para sempre: o `innerHTML` que o navegador devolve
     de um `<svg>` nunca volta igual ao que se escreveu, então a comparação do
     `escrever()` acusa mudança em todo tique — o mesmo tropeço que o alvo `cor`
     documenta para o CSSOM. E o desenho tem 50 KB; dois deles atravessam a
     ponte a cada meio segundo. */
  .gc-corpo .ds-mini{flex:0 0 48px;width:48px}
  /* cada bloco do corpo é uma dupla rótulo+campo, e a barra vertical separa
     irmãos — a mesma gramática das colunas dos outros dois quadros */
  .gc-bloco{display:flex;align-items:center;gap:8px;flex:0 0 auto}
  .gc-bloco.barra{padding-left:12px;margin-left:2px;border-left:1px solid var(--border-sutil)}
  .gc-bloco .rot{font-size:11.5px;font-weight:600;color:var(--rot-campo);white-space:nowrap;
                 display:flex;align-items:center;gap:6px}
  /* `.le` (a leitura "Vale Sem teto, do global, abaixo" ao lado do campo) SAIU
     em 28/08 — `D-O-SEM-TETO-SAI-DOS-DOIS-LUGARES`. A regra sai junto: CSS de
     elemento que não existe mais é a segunda versão viva de uma decisão. */
  .gc-corpo .btn{margin-left:auto;white-space:nowrap;flex:0 0 auto}
  /* REGRA DELA, escrita em `secao_controles.py:150`: *"sempre visível mas só
     acionável quando tiver no rádio"* — na linha do cabo o botão VAI, apagado,
     com a dica dizendo por quê. Botão que SOME ensina que a tela é instável. */
  .btn.apagado{border-color:var(--border-forte);color:var(--texto-mudo);
               opacity:.55;cursor:help}
  .btn.apagado:hover{border-color:var(--border-forte);color:var(--texto-mudo)}
  /* A TRAVA VIROU IRMÃ — 04/09/2026, e a razão é o vocabulário: UM `data-campo`
     por nó. O botão tinha o dele gasto na CLASSE (`luz-trava`), e por isso o
     `title` continuava sendo o do desenho — a dica dizia "este controle está no
     cabo" com o controle no rádio, e ao contrário. Estava escrito ali mesmo,
     como dívida: *"um segundo campo para o `title` pede outro elemento"*.

     ELE É ESSE OUTRO ELEMENTO. O `<i class="ltrava">` invisível recebe a classe
     e o botão fica com a DICA — que agora vem do produto inteira, com o aviso da
     mesa suja e a razão do carimbo de nascimento juntos
     (`a08_conexoes.dica_da_luz`). Zero pixel se move: a regra abaixo pinta o
     mesmo `.btn.apagado` de cima, pelo irmão.

     É O MESMO DESENHO dos `<i class="est">` das cinco linhas do exame, e pela
     mesma razão. */
  /* UMA LEITURA NO LUGAR DE UMA ESCOLHA — 04/09/2026, o escopo do botão físico
     do microfone. Ela ocupa a MESMA fatia que o `<select>` ocupava (mesma
     altura de linha, mesmo alinhamento), e a diferença é justamente a que se
     quer: nada aqui parece clicável, porque não há o que clicar.

     A GRAMÁTICA É A DA CASA para valor lido: peso normal, cor de texto, sem
     moldura — é o que separa "isto é uma resposta" de "isto é um campo". */
  .gc-corpo .leitura{font-size:11.5px;color:var(--texto-suave);white-space:nowrap;
                     cursor:help}
  .gc-corpo .ltrava{display:none}
  .gc-corpo .ltrava.on ~ .btn{border-color:var(--border-forte);color:var(--texto-mudo);
                              opacity:.55;cursor:help}
  /* o SVG real ganha a barra de luz acesa. A BARRA É PREENCHIDA, E NÃO
     CONTORNADA: estava `stroke:var(--luz)` com `stroke-width:1.2` numa forma de
     2×9,6px — metade do traço cai FORA da forma, e o que sobra dentro pinta
     menos de um pixel de cada lado. `fill` é o que a aba04 e a aba06 usam, e as
     duas acendem. Medido em 28/08/2026.
     AS LÂMPADAS DE JOGADOR SAEM DOS DESENHOS PEQUENOS — decisão dela, 28/08:
     neste tamanho elas medem 1,0 × 0,33 px, que é tinta que ninguém vê. Elas
     ficam nos desenhos grandes, da Iluminação.
     E SAEM DO DESENHO, não do CSS: quem as tira é `svg(..., lampadas=False)`.
     A regra `display:none` que morava aqui deixava as 24 no DOM — apagar não é
     tirar, e o grupo fora é o que não volta sozinho. */
  .gc-corpo [id$="-lightbar"] .peca{fill:var(--luz,var(--border-forte))}
  .acao{font-size:10.5px;color:var(--cyan);border-bottom:1px dotted var(--cyan);cursor:pointer}

  /* ---- o inventário da mesa: DUAS tabelas, ambas com cabeçalho roxo ---- */
  .tab{width:100%;border-collapse:collapse;font-size:11.5px}
  .tab th{color:var(--rot-campo);font-weight:600;text-align:left;font-weight:600;font-size:10px;
          padding:0 8px 6px 0;
          border-bottom:1px solid var(--border-forte)}
  .tab td{padding:6px 8px 6px 0;color:var(--texto-suave);border-bottom:1px solid var(--border-sutil)}
  .tab tr:last-child td{border-bottom:none}
  .tab .mudo{color:var(--texto-mudo)}
  /* CICATRIZ, medida em três tentativas: a `<table>` NÃO estica pela altura da
     caixa. Quem estica a linha de uma tabela é a `height` da CÉLULA, e não um
     `flex` na tabela.
     OS RÁDIOS VIZINHOS: UMA FILEIRA, e não mais uma tabela de duas linhas. A
     tabela custava 108px na coluna que MANDA na altura do quadro; a fileira
     custa 53. `grid-auto-flow:column` e não `repeat(4,…)`: o número de vizinhos
     vem da lista, e uma coluna digitada aqui mentiria no dia em que ela
     crescer — é a mesma forma que `.miolo .acoes` usa para os botões. */
  .vizinhos{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:11px}
  .vizinhos select.pronto{width:100%}
  .viz{display:flex;flex-direction:column;gap:4px;min-width:0}
  .viz .qual{font-size:10.5px;color:var(--texto-mudo);white-space:nowrap;overflow:hidden;
             text-overflow:ellipsis}
  /* A COLUNA "ONDE" — 04/09/2026, e ela é a que faltava para a linha do
     Check-up ter endereço na mesa. O exame diz "dois rádios da bancada estão em
     entradas vizinhas" e não diz QUAL; a janela estável põe o aviso ao lado do
     rádio culpado, e é isto.

     ELA NÃO CUSTA LINHA NOVA: o bloco `.viz` é uma coluna de 53px com o nome em
     cima e o `<select>` embaixo, e o "onde" entra como terceira linha de 10,5px
     — a mesma altura do nome. Quando não há aviso ele diz só o painel ("Direita",
     "Entrada 7" quando ela desenhou a mesa), e quando há, o aviso vem colado.

     O AMARELO SÓ ACENDE COM AVISO, e quem decide é o produto: o interruptor é
     um `<i>` invisível irmão, com o alvo `classe` BOOLEANO — o valor que ele
     recebe é a DICA de `_avisos_de_vizinhanca`, e o `ligado()` do piloto só
     pergunta se ela existe. Rádio que ninguém acusou recebe `""`, a classe
     apaga e a linha fica na cor de sempre. Nada aqui adivinha vizinhança.

     POR QUE UM IRMÃO E NÃO A PRÓPRIA LINHA: o vocabulário é UM `data-campo` por
     nó, e a linha já tem o dela (o texto). É o mesmo desenho dos `<i class="est">`
     das cinco linhas do exame, e do `~` que leva a cor do irmão até elas. */
  .viz .vaviso{display:none}
  .viz .onde{font-size:10.5px;color:var(--texto-mudo);white-space:nowrap;overflow:hidden;
             text-overflow:ellipsis}
  .viz .vaviso.on ~ .onde{color:var(--orange)}
  /* a sobra de altura das duas colunas do inventário cai ANTES da última fileira,
     nunca entre irmãos — `space-between` só empurra o buraco para o meio */
  .lado-e > .empurra,.lado-d > .empurra{margin-top:auto}

  /* ================= o orçamento do rádio =================
     UMA conta, e ela é uma régua de turnos por adaptador. O que está em uso vem
     na cor do PLÁSTICO de quem gastou; o microfone é a tampa laranja; e as
     VAGAS tracejadas são os controles da MESA que hoje estão no cabo.
     ------------------------------------------------------------------ */
  .capa{display:flex;align-items:center;gap:12px;height:var(--h-escolha)}
  .capa .rot{font-size:12px;font-weight:600;color:var(--rot-campo)}
  /* `.teto` (a leitura "Teto da vibração • Sem teto") e `.capa select.pronto` (o
     dropdown dos três perfis) SAÍRAM em 28/08 — a leitura por
     `D-O-SEM-TETO-SAI-DOS-DOIS-LUGARES`, o dropdown porque o teto global mudou-se
     para a aba Sistema como "Perfil de Bateria". As regras saem junto: CSS de
     elemento que não existe mais é a segunda versão viva de uma decisão.
     A CAPA CONTINUA COM `--h-escolha` (36px) MESMO SEM CAMPO, e isso é uma
     dívida ANOTADA, não uma escolha de desenho: o token existia para o rótulo
     ficar na linha de base do campo ao lado, e o campo saiu. Os dois títulos
     irmãos do MESMO quadro ("Adaptadores Bluetooth" e "Outros rádios na faixa de
     2,4 GHz") são `.linha-rot`, que ocupa 23px (19 de altura + 4 de margem) —
     13px a menos. Encolher não foi pedido e não é o que falta a nada hoje (a aba
     já cabe na janela dela com folga), então fica medido aqui em vez de mudado
     às escondidas. */
  .pista{display:flex;align-items:center;gap:12px;height:30px;font-size:11px}
  .pista .quem{flex:0 0 96px;color:var(--texto-suave);white-space:nowrap;
               overflow:hidden;text-overflow:ellipsis}
  .pista .trilho{flex:1;height:22px;border-radius:5px;background:var(--app-bg);
                 border:1px solid var(--border-sutil);display:flex;overflow:hidden}
  .pista .num{flex:0 0 128px;text-align:right;font-family:'JetBrains Mono',monospace;
              font-size:10.5px;color:var(--fg)}
  .pista .num i{font-style:normal;color:var(--texto-mudo)}
  .bloco{display:flex;align-items:center;justify-content:center;
         font-family:'JetBrains Mono',monospace;font-size:9.5px;overflow:hidden;white-space:nowrap}
  /* a cor do bloco é a do PLÁSTICO de quem gastou, e a do número é a que se lê
     em cima dela — nenhuma das duas digitada aqui.
     O FUNDO VEM INLINE, do dono da régua (`a08_conexoes.html_da_regua_do_radio`),
     e não de um `--plastico` cravado na página: quem não teve a cor lida fica
     com a neutra abaixo, que é a mesma promessa da borda da linha do controle. */
  .bloco.usa{background:var(--border-forte);font-weight:500}
  .bloco.mic{background:var(--orange);box-shadow:inset 1px 0 0 var(--app-bg)}
  /* a vaga é o que UM controle a mais custaria. Ela precisa fechar dos dois lados. */
  .bloco.vaga{border-left:1px dashed var(--border-forte);color:var(--texto-mudo);
    background:repeating-linear-gradient(135deg,transparent 0 5px,rgba(255,255,255,.03) 5px 10px)}
  .bloco.vaga:last-child{border-right:1px dashed var(--border-forte)}
  .pista .vazio{align-self:center;padding-left:9px;font-size:10.5px;color:var(--comment)}
  /* a régua de baixo: os mesmos recuos do trilho, para os números caírem no lugar */
  .eixo{display:flex;gap:12px;height:15px}
  .eixo .quem{flex:0 0 96px} .eixo .num{flex:0 0 128px}
  .eixo .regua{flex:1;display:flex;position:relative;
               font-family:'JetBrains Mono',monospace;font-size:9.5px;color:var(--comment)}
  .eixo .regua i{position:absolute;left:0;font-style:normal}
  .eixo .regua span{flex:1;text-align:right}
  .leg{display:flex;gap:16px;margin-top:8px;padding-left:108px;flex-wrap:wrap;
       font-size:10.5px;color:var(--texto-mudo)}
  .leg span{display:flex;align-items:center;gap:6px}
  .leg i{width:10px;height:10px;border-radius:2px;display:block;flex:0 0 10px}
  .leg i.vaga{border:1px dashed var(--border-forte)}

  /* OS DOIS BOTÕES DA MESA VIRARAM `<a href="#…">`, e um `<a>` chega sublinhado.
     Medido em 29/08: altura e largura ficaram iguais (34×539, os mesmos do
     `<button>`), e só o sublinhado mudou — o tipo de defeito que régua de caixa
     não vê, porque não move um pixel. O `CSS_POPUP` já carrega o mesmo remédio
     para o rodapé das pop-ups; aqui ele vale para o miolo. No dia em que uma
     segunda aba trocar botão por link, a regra sobe para o `topo.html` — que é
     a mesma conta que mudou o bloco das pop-ups de lugar hoje. */
  a.btn{text-decoration:none}

  /* ================= AS DUAS POP-UPS DA MESA =================
     A anatomia (`.tela-nova` -> `.tn-cx` -> `.tn-topo`/`.tn-corpo`/`.tn-rod`) NÃO
     está aqui: ela mudou-se para `monta.CSS_POPUP` em 29/08, quando esta aba
     virou o segundo consumidor dela. Aqui fica só o que é DESTAS duas telas.
     ---------------------------------------------------------------- */
  /* a rolagem é da `.moldura` (regra do `CSS_POPUP`); o respiro é para a barra
     não pintar por cima da última coluna de quadrados. */
  .tn-cx .moldura{padding-right:6px}
  .mm-rot{font-size:10px;font-weight:600;color:var(--purple);
          }
  .mm-rot-linha{display:flex;align-items:center;gap:8px;height:19px}

  /* ---- a lista de aparelhos.
     NO PRODUTO ELA É A COLUNA DA ESQUERDA e as faces ficam à direita
     (`mapa_da_mesa.py:515-523`). Aqui ela é a fileira de CIMA, e a razão é
     aritmética: o quadrado do produto tem 84px de largura e a fileira tem SETE
     colunas fixas — 7×84 + 6 de vão pedem 618px, e a `.tn-cx` oferece 624 por
     dentro. Lado a lado com uma coluna de lista, o quadrado cairia para ~56px e
     as três linhas de texto dele parariam de caber. Empilhado, o 84 do produto
     é exatamente o que sobra. */
  .mm-lista{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-bottom:12px}
  .mm-ap{height:26px;padding:0 9px;border-radius:6px;background:var(--elevated);
         border:1px solid var(--border-forte);color:var(--texto-suave);
         font:inherit;font-size:11px;cursor:pointer;display:inline-flex;
         align-items:center;gap:4px}
  .mm-ap code{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--texto-mudo)}
  .mm-ap:hover{border-color:var(--comment);color:var(--fg)}
  /* o escolhido é um ToggleButton ATIVO — clicar nele de novo desescolhe. */
  .mm-ap.on{border-color:var(--purple);background:var(--sel-bg);color:var(--fg);font-weight:600}
  .mm-ap.on code{color:var(--purple)}

  /* ---- as faces */
  .mm-face{margin-bottom:12px}
  .mm-face-cab{display:flex;align-items:center;gap:9px;margin-bottom:6px}
  .mm-face-nome{font-size:11.5px;font-weight:600;color:var(--texto-suave)}
  /* o nome é um `Gtk.Label`, NÃO um campo: depois de criada, a face não tem
     como ser renomeada nem apagada pela interface (`mapa_da_mesa.py:645`). */
  .tn-cx .mm-face-cab .btn{height:23px;font-size:10px;padding:0 8px}
  /* SETE COLUNAS, para toda face, e o produto escreve a razão: "sete é a fileira
     do hub dela, que é a maior face desta casa" (`_COLUNAS = 7`). O `minmax` deixa
     o quadrado encolher em vez de rolar de lado quando a barra vertical aparece. */
  /* COLUNAS DE VERDADE — 31/08/2026: *"ajusta os alinhamentos e distribuições de
     tudo"*. A grade já era `repeat(7, …)`, mas a filha empilhada dentro da célula
     furava a coluna: medido, 8 x diferentes numa grade de 7, e dois quadrados de
     larguras diferentes (82 e 73). Com a filha fora, toda entrada é uma célula de
     uma coluna, e as duas faces alinham na mesma régua de x. */
  .mm-grade{display:grid;grid-template-columns:repeat(7,minmax(0,84px));
            gap:5px;align-items:start;justify-content:start}
  /* o hub carrega uma legenda embaixo, então a célula dele é mais larga */
  .mm-grade-hubs{grid-template-columns:repeat(3,minmax(0,148px))}
  .mm-ligado{font-size:10px;color:var(--texto-mudo);line-height:1.4;padding-left:2px}
  .mm-ligado b{color:var(--texto-suave);font-weight:600}
  .mm-cel{display:flex;flex-direction:column;gap:4px}
  /* 84×56 é `botao.set_size_request(84, 56)`, que em GTK é MÍNIMO e não teto —
     por isso `min-height` aqui, e não `height`: "Aparelho de entrada" quebra em
     duas linhas nos dois. */
  .mm-sq{min-height:56px;width:100%;padding:4px 3px;border-radius:6px;
         background:var(--app-bg);border:1px solid var(--border-forte);
         color:var(--texto-suave);font:inherit;cursor:pointer;
         display:flex;flex-direction:column;align-items:center;justify-content:center;
         gap:1px;text-align:center;line-height:1.15;overflow:hidden}
  .mm-n{font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:700;color:var(--fg)}
  .mm-c{font-size:9px;color:var(--texto-suave);word-break:break-word}
  .mm-c.mm-vazia{color:var(--texto-mudo);font-style:italic}
  .mm-ext{font-size:8.5px;color:var(--comment)}
  .mm-v{font-size:9px;font-weight:600}
  /* AS CINCO CORES SÃO OS CINCO ESTADOS QUE **ESTA** JANELA PRODUZ. Os três do
     modo ideal (`chega`, `sai`, `fica`) não entram: eles vêm do plano, e esta
     janela não calcula plano nenhum. */
  .mm-sq[data-v="cheia"]{opacity:.72}
  .mm-sq[data-v="cheia"] .mm-v{color:var(--texto-mudo)}
  .mm-sq[data-v="serve"]{border-color:var(--comment)}
  .mm-sq[data-v="serve"] .mm-v{color:var(--comment)}
  .mm-sq[data-v="evite"]{border-color:var(--orange)}
  .mm-sq[data-v="evite"] .mm-v{color:var(--orange)}
  .mm-sq[data-v="melhor"]{border-color:var(--green);background:rgba(80,250,123,.07)}
  .mm-sq[data-v="melhor"] .mm-v{color:var(--green)}
  /* a filha por extensão é recuada e tracejada: ela não está na fileira do metal,
     está na ponta de um cabo que só VOCÊ sabe que existe. */
  .mm-sq.mm-filha,.mm-cel .mm-sq + .mm-sq{border-style:dashed;margin-left:9px;width:calc(100% - 9px)}

  /* ---- as duas perguntas da sala, que se mudaram da aba para cá em 28/08.
     NENHUMA `.dica` MORA AQUI DENTRO, e isso é uma correção medida em 29/08.
     A primeira versão pôs um `?` no rótulo da lista, um no rótulo deste bloco e
     um em cada pergunta — quatro no total, os quatro dentro da `.moldura`. A
     régua reprovou: o envelope mediu 860,2×762,5px contra a janela de 757, e
     duas das dicas fechavam em y=810. Os dois modos de errar de uma vez: a
     `.moldura` rola, e um ancestral que rola RECORTA todo descendente absoluto;
     e um `?` a 670px de altura abre uma caixa de 141px que sai da janela pela
     base. É a mesma cicatriz que o `CSS_POPUP` já carrega escrita — "não há uma
     só dica dentro dela". A cura: um `?` por pop-up, no `.tn-topo`, e o resto
     em `title`, que é hover nativo e não tem caixa a recortar. */
  .mm-sala{margin:14px 0 12px}
  /* EMPILHADA, e não lado a lado: a pergunta mais longa tem 46 caracteres e a
     fileira das três opções mede 350px — numa caixa de 624px por dentro, lado a
     lado o enunciado caía para quatro linhas de nove caracteres. */
  /* PERGUNTA E BOTÕES NA MESMA LINHA — medido em 29/08. Empilhados, os dois
     blocos custavam 133px e a confissão nascia FORA da vista (a moldura mostra
     478 de 658). O enunciado mais longo mede ~250px e a fileira das três opções
     350px: 600 numa caixa de 624 por dentro. As perguntas continuam uma ABAIXO
     da outra — o que ficou lado a lado é o enunciado e a sua resposta, que é o
     par que se lê junto. */
  .mm-perg{display:flex;align-items:center;gap:10px;margin-top:9px}
  .mm-perg > .mm-q{flex:1;min-width:0}
  .mm-q{font-size:11.5px;color:var(--texto-suave);display:flex;align-items:center;gap:7px}
  /* o `.seg` do esqueleto dá `flex:1;min-width:150px` a cada opção, para uma
     fileira que ocupa a coluna inteira. Aqui são TRÊS opções de uma a três
     palavras numa caixa de 624px: esticadas, cada botão media 200px de fundo  (noqa-acento: verbo medir, imperfeito)
     para 20 de texto. Elas passam a caber no que dizem. */
  .tn-cx .mm-sala .seg button{flex:0 0 auto;min-width:92px;height:28px;
                              font-size:11px;padding:0 14px}

  /* ---- a confissão. Ela NUNCA é vazia depois da primeira face.
     ELA SAIU DO CORPO E VIROU DICA — decisão dela, 29/08/2026, e é a
     `D-TUDO-QUE-EXPLICA-VIRA-DICA` aplicada a esta pop-up. O que a comprou:
     a moldura escondia 140px, e o PRIMEIRO deles era a confissão inteira
     (o bloco de lista media 106px). Uma tela que parece completa e não está  (noqa-acento: verbo medir, imperfeito)
     é a classe de defeito que esta casa mais paga.

     O QUE FICA NO CORPO, E POR QUE FICA: uma linha só, sempre à vista, com a
     CONTA. Sumir calada é que era o defeito — a confissão é o que ensina o que
     o Hefesto não sabe. A linha nasce FORA da `.moldura` de propósito: dentro
     dela voltaria a rolar para baixo da dobra, que é justamente o que se está
     consertando.

     E O SINAL **NÃO É UM `?`** — nem podia ser, por duas contas medidas:
       · a regra desta pop-up é "um `?` por pop-up, no `.tn-topo`" (ver o
         comentário do `.mm-sala`: um `?` a 670px abre caixa de 141px que sai
         da janela pela base, e esta linha vive a ~600px);
       · e um `?` mudo não diz NADA antes do hover. A linha diz a conta —
         "três coisas" — de graça, para quem nunca passar o mouse. O rastro
         sobrevive sem interação nenhuma, que é o que a decisão exige.
     O resto é `title`: hover nativo, sem caixa nossa a recortar nem a
     transbordar. O `cursor:help` e o sublinhado pontilhado são o que anuncia
     que há mais ali. */
  .mm-conf-linha{margin:11px 0 0;font-size:11.5px;line-height:1.55;
                 color:var(--texto-mudo)}
  .mm-conf-linha b{font-weight:600;color:var(--texto-suave)}
  .mm-conf-linha span{cursor:help;border-bottom:1px dotted var(--border-forte)}
  /* A LINHA SOME QUANDO NÃO HÁ O QUE CONFESSAR — 03/09/2026, e a regra é a da
     janela do desenho: lá `confissao_do_desenho` devolve vazio e nada é
     desenhado. Quem acende esta classe é o produto, pelo `confissao-nada`; no
     arquivo aberto no navegador ela nunca está ligada, porque a cena tem
     lacuna. Sem esta regra, uma mesa sem lacuna leria "…: nada." — texto que
     ocupa a linha para não dizer nada. */
  .mm-conf-linha.sumido{display:none}

  /* ---- os gestos de baixo. `.apagado` deixou de ser só da Gestão de Controles:
     os dois botões de ação desta pop-up nascem apagados pela mesma regra dela —
     botão que SOME ensina que a tela é instável. */
  /* OS DOIS GESTOS TÊM O MESMO TAMANHO — 31/08/2026, parte do *"ajusta os
     alinhamentos e distribuições de tudo"*. Eles medem o texto: `Tirar daqui`
     dava 92px e `Tem uma extensão aqui` 170, lado a lado, e dois botões do mesmo
     peso com tamanhos tão diferentes leem como hierarquia que não existe — os
     dois agem sobre a MESMA entrada que você acabou de clicar.
     O grupo de criar face continua empurrado à direita: ele não age sobre a
     entrada selecionada, e a distância é o que diz isso. */
  .mm-acoes{display:flex;align-items:center;gap:8px}
  .mm-acoes > .btn{flex:0 0 auto;min-width:172px;justify-content:center}
  .mm-nova{display:flex;align-items:center;gap:8px;margin-left:auto}
  .mm-campo{height:var(--h-acao);width:118px;padding:0 9px;border-radius:7px;
            background:var(--app-bg);border:1px solid var(--border-forte);
            color:var(--fg);font:inherit;font-size:11.5px}
  .mm-campo::placeholder{color:var(--texto-mudo)}
  .mm-aplicar{margin:11px 0 0}
  .tn-rod.mm-rod{justify-content:flex-end}
  .tn-rod.mm-rod .btn{flex:0 0 auto;padding:0 22px}

  /* ================= a cerimônia de um toque por aparelho ================= */
  .ce-cartao{display:flex;flex-direction:column;gap:6px;padding:14px 15px;
             border-radius:8px;background:var(--app-bg);
             border:1px solid var(--border-sutil)}
  .ce-perg{font-size:15px;font-weight:600;color:var(--fg);line-height:1.35}
  /* TEXTO, nunca barra: os DOIS números, sempre (R26). E não há barra de
     progresso porque o total da fase em pé ENCOLHE — ela andaria para trás. */
  .ce-cont{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--purple)}
  .ce-quem{font-size:11.5px;color:var(--texto-suave);line-height:1.55}
  .ce-quem code{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--texto-mudo)}
  /* OS LUGARES CABEM NUMA LINHA SÓ — 31/08/2026, e ela mandou com a foto na mão:
     *"botões em duas linhas. deveria ser uma."*

     A causa era `flex-wrap:wrap` com botões do tamanho do próprio texto: some a
     largura dos quatro (`Frente do gabinete` é 40% maior que `Em cima da mesa`)
     e, no dia em que a soma passa da caixa, o último cai sozinho para a segunda
     linha. Depende da FONTE que carregou — por isso a foto dela mostrava duas
     linhas e o Chrome headless mostrava uma: com fallback mais estreito, cabia.
     Régua nenhuma pegaria isso; só o olho dela, na máquina dela.

     `grid-auto-flow:column` com `grid-auto-columns:1fr` é a gramática que a casa
     já usa em `.miolo .acoes`: os botões dividem a largura em partes iguais,
     nunca quebram, e o alvo de clique é o mesmo para as quatro escolhas — que é
     o que quatro escolhas do mesmo peso pedem. */
  .ce-botoes{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:8px;margin-top:12px}
  .tn-cx .ce-botoes .btn{width:100%;text-decoration:none;justify-content:center;
                         padding:0 6px;min-width:0}
  /* o foco É o anúncio (R13): não há live region alcançável pelo PyGObject, então
     mover o foco é a única forma que a janela tem de dizer "o passo mudou". */
  .btn.foco{outline:2px solid var(--purple);outline-offset:2px}
  .ce-relogios{font-size:10.5px;color:var(--texto-mudo);line-height:1.55;margin-top:13px}
"""


#: A largura da coluna do nome, medida no Chrome em 28/08: o mais largo dos
#: rótulos da mesa é o do P3 ("Sony • Player 3 • Galactic Purple • BT"), com
#: 214,3px. 220 dá 5,7 de folga — uma palavra maior nessa linha estoura, e aí é
#: este número que sobe, num lugar só.
LARG_NOME = 220
CSS += f"\n  .gc-cabeca{{--larg-nome:{LARG_NOME}px}}\n"

# ---------------------------------------------------------------------------
# AS REGRAS QUE O ACORDEÃO GERA — uma por estado, e o estado é a MESA.
#
# Duas coisas saem daqui, e as duas são a decisão dela de 28/08:
#   1. a linha ABERTA é a da fita, e clicar numa linha MUDA A FITA;
#   2. o chip "Todos" abre os quatro.
#
# A FITA É DO `monta.fita()`, e esta aba não a escreve — ela repinta os chips
# pela posição, que é derivada da MESA e não digitada. O primeiro filho do
# `.fita` é o rótulo "Ajustes vão para:", o segundo é o chip "Todos", e daí em
# diante vem um por controle, na ordem da mesa.
#
# O QUE O MOCKUP NÃO CONSEGUE, e é honesto dizer: o chip da fita é um `<span>`
# do esqueleto, e um `<span>` não vira alvo de clique sem tocar o `monta.py`.
# O gesto "voltar para Todos" existe e está no lugar mais próximo — a própria
# própria linha aberta —, com o `title` dizendo o que ele faz.
# ---------------------------------------------------------------------------
#: Um rádio por controle QUE ABRE, mais o "todos". Gerar um para quem não
#: está na mesa deixaria no CSS uma regra que nenhum label pode disparar —
#: e regra que ninguém alcança é a mesma coisa que régua que casa zero.
ESTADOS = ["todos"] + [c["pref"] for c in CONECTADOS]

_regras = [
    "  /* o destaque estático da fita perde para o do acordeão: `.fita .chip.on`",
    "     tem especificidade maior que o `.chip.on` do esqueleto, e é ele que",
    "     apaga o chip que nasceu marcado no HTML. */",
    "  .fita .chip.on{background:var(--app-bg);color:var(--texto-mudo);font-weight:400;"
    "border-color:var(--border-forte)}",
    "  .fita .chip.plastico.on{border-color:var(--plastico,var(--border-forte))}",
    "  /* o corpo do controle que a fita aponta */",
    "  .quadro-corpo:has(#gc-todos:checked) .gc-corpo{height:40px;padding:2px 12px}",
    "  /* NO ESTADO “Todos” AS QUATRO JÁ ESTÃO ABERTAS: a seta de abrir sai, e no",
    "     lugar dela entra a palavra do gesto que ali existe — estreitar para um. */",
    "  .quadro-corpo:has(#gc-todos:checked) .gc-seta.abre{display:none}",
    "  .quadro-corpo:has(#gc-todos:checked) .gc-seta.so{display:flex}",
]
for i, estado in enumerate(ESTADOS):
    n = 2 + i  # o chip deste estado, na fita
    _regras.append(
        f"  body:has(#gc-{estado}:checked) .fita .chip:nth-child({n})"
        "{background:var(--sel-bg);color:var(--fg);font-weight:600;border-color:var(--purple)}")
    _regras.append(
        f"  body:has(#gc-{estado}:checked) .fita .chip.plastico:nth-child({n})"
        "{border-color:var(--plastico,var(--border-forte))}")
    if estado == "todos":
        continue
    _regras.append(f"  .quadro-corpo:has(#gc-{estado}:checked) .gc-{estado} .gc-corpo"
                   "{height:40px;padding:2px 12px}")
    _regras.append(f"  .quadro-corpo:has(#gc-{estado}:checked) .gc-{estado} .gc-seta.abre{{display:none}}")
    _regras.append(f"  .quadro-corpo:has(#gc-{estado}:checked) .gc-{estado} .gc-seta.fecha{{display:flex}}")
    _regras.append(
        f"  .quadro-corpo:has(#gc-{estado}:checked) .gc-{estado}"
        "{background:linear-gradient(0deg,var(--sel-bg),var(--sel-bg)),var(--app-bg)}")
CSS += "\n" + "\n".join(_regras) + "\n"

# ---------------------------------------------------------------------------
# A PORTA PARA O BANCO DE PROVAS — `.porta`, 29/08/2026.
#
# DEFEITO MEDIDO: `mapa-das-portas.html` tem 1475 linhas e é o desenho do motor
# do arranjo — o mesmo motor que hoje roda em Python
# (`integrations/arranjo_da_mesa.py`, `mapa_das_portas.py`,
# `censo_do_gabinete.py`) — e `grep -c 'mapa-das-portas' layout/??-*.html`
# devolve **0 nas dez abas**. Só se chega nele digitando o caminho.
#
# Ele é o banco de provas DESTE quadro: as entradas do gabinete, os
# adaptadores, os arranjos possíveis e a conta das 1600 fatias. A porta fica no
# `.quadro-topo` de "Rádio e adaptadores", empurrada à direita, e não é padrão
# novo: é o mesmo `margin-left:auto` do `.sensores` da aba Controles.
#
# A ALTURA É TRAVADA EM 17px, e o número é medido na aba Navegação, onde esta
# mesma porta nasceu: o `.quadro-topo` é `align-items:center`, o
# `.quadro-titulo` mede 17px, e uma pastilha com borda de 19px derrubou o quadro
# inteiro 2px — 663 das 733 caixas da aba mudaram de lugar. Sem borda e sem
# preenchimento, a medição de antes e depois bate caixa a caixa.
CSS += """
  .porta{margin-left:auto;font-size:11px;line-height:17px;height:17px;
    color:var(--texto-mudo);text-decoration:none;white-space:nowrap}
  .porta:hover{color:var(--cyan);text-decoration:underline}
"""


#: "VER AS ORDENS IGNORADAS", e não "caladas" — corrigido em 28/08.
#:
#: Ela escreveu a fileira de botões com todas as letras: *"Examinar de novo. /
#: Já Movi - Reexaminar. / Ignorar / Ver Ordens ignoradas."* A tela dizia "Ver as
#: ordens caladas", e o defeito é de PAR: o botão irmão — o que produz a ordem
#: nesse estado — chama-se **Ignorar**. Quem aperta "Ignorar" procura depois as
#: ordens *ignoradas*, não as *caladas*: "caladas" era a única palavra da dupla
#: sem par na tela, e nenhuma outra frase da aba a sustentava.
#:
#: O nome fica num lugar só porque ele aparece em TRÊS: o botão, a linha CERTO do
#: exame ("elas voltam em …") e a dica do próprio "Ignorar". Uma correção pela
#: metade deixaria as duas palavras vivas, que é o defeito que a regra da casa
#: existe para matar.
VER_IGNORADAS = "Ver as ordens ignoradas"

#: AS DUAS JANELAS DA MESA — `D-MAPEAR-ENTRADAS-E-NAO-PORTAS` (28/08).
#:
#: Ela pediu "Mapear Portas" e "Mapear Porta a Porta". Vista a colisão com a
#: `D-A-PALAVRA-ENTRADA` (24/08, que saiu de uma frase dela mesma — *"o número da
#: entrada usb salvaria muito como coluna"* — e diz que a aba fala **entrada**,
#: nunca **porta**, para não colidir com porta de rede), ela escolheu manter
#: "entrada": *"Desenhar a minha mesa"* vira **Mapear Entradas**, e *"Ensinar as
#: minhas entradas"* vira **Mapear Entrada a Entrada**.
#:
#: O NOME FICA NUM LUGAR SÓ porque cada um aparece em quatro: o botão, o `?` do
#: quadro que o hospeda, o `?` do "Está tudo certo?" (que manda as duas perguntas
#: da sala para lá) e a legenda. As dicas dos dois botões continuam valendo —
#: nenhum deles mudou de função, só de nome.
MAPEAR_ENTRADAS = "Mapear Entradas"
MAPEAR_UMA_A_UMA = "Mapear Entrada a Entrada"

#: O botão que sobrou dos quatro do Check-up, já na seção das entradas.
#:
#: A PALAVRA "PORTAS" É DELA, e ela colide com a `D-A-PALAVRA-ENTRADA` (24/08),
#: que fixou **entrada** para não confundir com porta de rede. A colisão está
#: ANOTADA e não resolvida por mim: quem escolheu "porta" aqui foi ela, no mesmo
#: turno em que mandou o botão descer, e a seção de destino já hospeda o link
#: *"Banco de provas: o mapa das portas"* — a palavra já vive ali.
EXAMINAR_PORTAS = "Examinar Portas"

#: A DICA DO CAMPO DE NOME — e ela mudou de casa em 04/09/2026, com a tabela:
#: quem a escreve na tela viva é `a08_conexoes._html_dos_adaptadores`, então o
#: dono passou a ser o pacote. A razão dela (*"tirar o botão Renomear e
#: adicionar a possibilidade de renomear dando duplo clique no nome"*, 31/08)
#: está lá, com o resto.
RENOMEAR_DICA = _pacote08.RENOMEAR_DICA


#: O ESTADO DA SEGUNDA LINHA DO EXAME, e ele é constante por um motivo de
#: ferramenta: os `exame(...)` do desenho moram DENTRO do f-string que monta a
#: aba, e o estado é chave de máquina do `exame_da_mesa.Item` — ASCII por
#: contrato. O `validar-acentuacao.py` isenta a LINHA que traga `noqa-acento`, e
#: uma linha de dentro do f-string não pode trazer comentário nenhum: ele sairia
#: impresso no HTML. Aqui fora, a isenção cabe e diz por quê.
#:
#: Os outros três estados do mapa não precisam disto: dois deles não levam
#: acento, e o terceiro vem colado num `_`, que é o que a régua de acentuação
#: já não cobra.
_ATENCAO = "atencao"  # noqa-acento (chave de máquina do exame, ASCII por contrato)


#: A CLASSE DE CADA ESTADO NA LINHA DE VEREDITO. O nome é `vst` e não `est` para
#: não colidir com os interruptores das cinco linhas do exame — os dois grupos
#: vivem na mesma seção, e um `~` que atravessasse os dois pintaria a linha de
#: cima com a cor de uma linha de baixo.
#:
#: A ORDEM É A DO PACOTE (`a08_conexoes.ENDERECO_DO_VEREDITO`), e os endereços
#: saem de lá: digitar os quatro aqui seria a segunda grafia do vocabulário que
#: o pacote emite, e a primeira coisa que uma segunda grafia perde é o dia em
#: que a outra muda.
_CLASSE_DO_VEREDITO = {"certo": "ok", "atencao": "warn",  # noqa-acento (chave de máquina do exame)
                       "problema": "bad", "nao_sei": "info"}


def veredito_do_checkup(estado, frase):
    """A linha de veredito do topo do Check-up — **D-16 dela**, 04/09/2026.

    *"Uma linha de veredito no topo."* · *"Na cor do pior achado."*

    `estado` é o estado do exame que o DESENHO mostra em repouso, e `frase` é a
    frase dele. Os dois são de bancada, como as cinco linhas abaixo: o mockup é
    HTML estático e ninguém o pinta quando ela o abre no navegador, então uma
    linha que o produto ainda não preencheu tem de continuar parecendo o que
    parecia.

    NA TELA VIVA OS DOIS VÊM DO PRODUTO: a frase de `ordens_da_mesa.cabecalho()`
    — que é o dono das quatro — e o estado de `secao_exame.o_mais_grave` sobre
    ela e sobre `exame_da_mesa.veredito()`. Ver `a08_conexoes._veredito_do_exame`.

    O PONTO É UM ELEMENTO E NÃO UM `::before`, e a razão é o combinador: a cor
    chega pelo `~` a partir do interruptor irmão, e um pseudo-elemento não é
    irmão de ninguém.
    """
    interruptores = "".join(
        f'<i class="vst vst-{_CLASSE_DO_VEREDITO[e]}'
        f'{" on" if e == estado else ""}" data-campo="{endereco}" '
        f'data-hef-alvo="classe" data-hef-quando="{e}"></i>'
        for e, endereco in _pacote08.ENDERECO_DO_VEREDITO.items())
    return (f'        <div class="veredito">{interruptores}'
            f'<span class="ponto"></span>'
            f'<span class="txt" data-campo="veredito">{frase}</span></div>')


def exame(estado, txt, dica, linha=0):
    """Uma linha do exame: o selo, o que ele achou, o `?` e o gesto de ignorar.

    `estado` É O ESTADO DO EXAME, e não mais a classe CSS — 03/09/2026. A classe
    e a palavra saem de `gui.aba_conexoes.SELO_DO_ESTADO`, que é o dono do mapa e
    já era quem o produto consultava; digitá-las aqui era a segunda grafia, a que
    fica para trás no dia em que a primeira mudar. O desenho passa a dizer o que
    a linha É, e a folha de estilo diz como isso se parece.

    O IGNORAR SAIU DA FILEIRA E VIROU GLIFO NA LINHA — 31/08/2026, decisão dela:
    *"ignorar e ver ordens ignoradas … são referentes ao check-up, então colocar
    um botão pra ignorar no formato de glifo ali"*. E ela tem razão pelo que o
    botão FAZIA: um `Ignorar` no rodapé do quadro não dizia O QUÊ ignorar — havia
    cinco linhas e um botão só. Na linha, o gesto tem sujeito.

    `linha` É O SUJEITO DO CLIQUE, e ele precisou existir em 01/09/2026 para o
    ⊘ deixar de ser botão morto. O ouvinte do piloto manda `data-v` e o
    `textContent` do que foi clicado; o `textContent` do ⊘ é "⊘" nas cinco
    linhas, e o `closest('[data-controle],[data-uniq]')` não acha nada aqui —
    então, sem este número, as cinco linhas mandavam **o mesmo clique**.
    Ignorar a segunda calaria a que estivesse no lugar da primeira.

    É a POSIÇÃO e não a chave da regra porque o HTML é estático: as cinco
    linhas nascem com o achado do desenho e são repintadas a cada tique com o
    exame da mesa dela (a pintura distribui a lista pelos elementos de mesmo
    `data-campo`, na ordem). Quem sabe QUAL achado caiu na posição 2 é quem
    pintou — `a08_conexoes.pacote()` —, e é lá que o número vira ordem de
    serviço.

    O `?` GANHOU ENDEREÇO em 02/09/2026, e ele era a metade MENTIROSA da linha.
    O selo e o `<span class="txt">` já eram repintados com o exame da mesa
    dela; a dica ao lado continuava sendo a do DESENHO. Fotografado nesta
    bancada, com dois controles na mesa: a linha 1 dizia **"Economia de energia
    desligada"** (achado dela) e o `?` ao lado explicava *"as entradas em uso
    entregam 500 mA ou mais"* — a medição de OUTRO achado. E nas posições que o
    exame não preencheu, o texto ficava `—` com o `?` ainda contando os quatro
    rádios vizinhos do mockup.

    O ALVO É `html`, e pela mesma razão do `teto-explica`: a dica do produto
    traz `<b>` e `<br>`, e o `textContent` do ramo padrão escreveria os
    marcadores como texto literal.

    A PÍLULA GANHOU DOIS ENDEREÇOS, E SÃO DOIS ELEMENTOS — 02/09/2026, o quarto
    selo dela. A palavra continua em `data-campo="selo"`; o ESTADO entrou em
    `data-campo="selo-estado"`, com alvo `classe`. **Um elemento só não dava**:
    o vocabulário é UM `data-campo` por nó, e a palavra e a cor são dois dados
    diferentes do mesmo selo. Por isso a palavra desceu para um `<span>` filho
    — inline e sem estilo próprio, então nada muda um pixel — e a pílula de
    fora ficou com a classe.

    `data-hef-quando="problema"` é o gatilho, e ele lê o ESTADO do exame, não a
    classe CSS: quem traduz estado em cor é esta folha de estilo (`.selo.grave`,
    acima), e é aqui que essa decisão tem de morar.

    **O QUE ELE NÃO CURAVA, E AGORA CURA — 03/09/2026.** A frase que estava aqui
    dizia que as três classes do desenho (`ok`/`warn`/`info`) continuavam
    CRAVADAS por posição, e que isso *"pede um endereço por estado, não um"*. Ele
    ganhou os endereços: os três `<i class="est">` invisíveis abaixo, um por
    estado, com o `data-campo` que `a08_conexoes.ENDERECO_DO_ESTADO` nomeia. O
    quarto continua na pílula, porque `problema` é ACRÉSCIMO de cor e não troca.

    O DEFEITO QUE ELES FECHAM, fotografado na mesa dela: com os três achados
    `certo` do exame de hoje, a segunda linha mostrava a palavra **CERTO** dentro
    da pílula **laranja** — a cor que o mockup cravou naquela posição.

    OS `<i>` NASCEM COM A COR DO DESENHO ACESA (`on` no que casa com `estado`),
    e as classes cravadas da pílula FICAM: o mockup é HTML estático, ninguém o
    pinta quando ela o abre no navegador, e uma linha que o produto não
    preencheu tem de continuar parecendo o que parecia.
    """
    classe, palavra = _aba_conexoes.SELO_DO_ESTADO[estado]
    # UM INTERRUPTOR POR ESTADO, menos o `problema` — ele é a própria pílula.
    # A ORDEM É A DO MAPA, e o `data-hef-quando` é a chave de máquina do exame:
    # é ela que o `escrever()` compara com o que o pacote emite.
    interruptores = "".join(
        f'<i class="est est-{_aba_conexoes.SELO_DO_ESTADO[e][0]}'
        f'{" on" if e == estado else ""}" data-campo="{endereco}" '
        f'data-hef-alvo="classe" data-hef-quando="{e}"></i>'
        for e, endereco in _pacote08.ENDERECO_DO_ESTADO.items()
        if endereco != "selo-estado")
    return f'''          <div class="exame" data-campo="exame">
            {interruptores}
            <span class="selo {classe}" data-campo="selo-estado" data-hef-alvo="classe" data-hef-classe="grave" data-hef-quando="problema"><span data-campo="selo">{palavra}</span></span>
            <span class="txt" data-campo="achado">{txt}</span>
            <span class="ajuda">?<span class="dica" data-campo="achado-explica" data-hef-alvo="html">{dica}</span></span>
            <button class="ignora" data-gesto="ignorar" data-v="{linha}" title="Ignora ESTE conselho enquanto os cabos estiverem assim. A linha fica apagada aqui, e volta sozinha se o arranjo mudar.">⊘</button>
          </div>'''


#: UM BLOCO POR VIZINHO, os quatro numa fileira só — e não mais uma tabela de
#: duas linhas. Nada se perdeu: o nome cru continua em cima, a resposta continua
#: embaixo, e o "O que é" que era cabeçalho de coluna virou o que sempre foi — a
#: pergunta que o próprio campo faz.
def viz_bloco(nome, escolha, pergunta=False, linha=0):
    """Um vizinho: o nome cru que o sistema entrega, e o que ELA diz que ele é.

    `linha` tem a mesma razão do `linha` do :func:`exame`, e o mesmo preço se
    faltar: os quatro `<select>` são iguais e o ouvinte não teria como dizer
    qual mudou — declarar "isto é um teclado" gravaria no rádio errado.

    O que endereça o rádio no `maquina.json` é `vid:pid`
    (`MesaDeclarada._chave_de_radio_e_vid_pid`), e ele NÃO cabe aqui: os quatro
    blocos são HTML estático e o par só se sabe depois de ler o barramento. Quem
    lê é `a08_conexoes.pacote()`, que pinta o nome e guarda a ordem — a posição
    é a ponte entre o desenho e a mesa dela.
    """
    d = ("O sistema entrega o nome cru e não sabe o que é. Com o nome, o Hefesto sabe o que dá "
         "para desligar e o que não dá. “Outro” abre um campo para você escrever."
         if pergunta else
         "O que é este rádio. Mudar a resposta aqui já é corrigi-la. “Outro” abre um campo "
         "para você escrever o nome.")
    c = "pronto pergunta" if pergunta else "pronto"
    # A TERCEIRA LINHA DO BLOCO — 04/09/2026: ONDE aquele rádio está, com o aviso
    # de vizinhança colado quando há um. Os dois donos são do produto
    # (`secao_mesa._onde_esta_o_radio` e `secao_mesa._avisos_de_vizinhanca`), e
    # nesta bancada UM dos três rádios acusa: *"Não sei · vizinho do adaptador
    # 3"*. É o mesmo fato que a linha do Check-up chama de "dois rádios da
    # bancada estão em entradas vizinhas" — e que ali não diz qual dos rádios é.
    #
    # NO DESENHO ELE FICA MUDO, e é a mesma regra dos `<i class="est">`: o mockup
    # é HTML estático, ninguém o pinta quando ela o abre no navegador, e uma cena
    # de bancada não tem como saber a entrada de um rádio que não existe. O
    # travessão é a palavra da casa para "sem dado" (`gui.aba_conexoes.TRACO`).
    return (f'              <div class="viz">'
            f'<span class="qual" data-campo="vizinho-nome" title="{nome}">{nome}</span>'
            f'<select class="{c}" title="{d}" data-gesto="vizinho-o-que-e" data-v="{linha}"'
            f' data-campo="vizinho-tipo" data-hef-alvo="valor">'
            f'{viz_sel(escolha)}</select>'
            f'<i class="vaviso" data-campo="vizinho-onde-dica" data-hef-alvo="classe"></i>'
            f'<span class="onde" data-campo="vizinho-onde">'
            f'{_aba_conexoes.TRACO}</span></div>')


# ---------------------------------------------------------------------------
# UM CONTROLE DO ACORDEÃO — uma função, N chamadas, zero texto repetido.
# ---------------------------------------------------------------------------
#: A FRASE QUE CADUCOU, e por que a nova fala de NÓS e não do aparelho.
#:
#: Esta aba dizia, em dois lugares, que *"pelo rádio o aparelho recusa a
#: leitura"* da cor. **Não recusa.** Medido nesta bancada em 27/08/2026, no cabo
#: e no rádio, com o serial saindo dos dois (`hidraw8`, rádio, `F55602…`, Cosmic
#: Red, aceita): o que travava era a semente do NOSSO CRC — `0x53`
#: (`SET_REPORT|FEATURE`), e não `0xA3` (`DATA|FEATURE`), que foi a de 23/08.
#: Ver `docs/protocol/dualsense-referencia-canonica.md:1574-1663`.
#:
#: MAS A CURA AINDA NÃO ESTÁ NO PRODUTO — ela é a `ONDA-CONEXOES-11`. Por isso a
#: frase nova não promete leitura pelo rádio: ela diz o que É verdade hoje, que é
#: que **nós ainda não perguntamos**. Só o "ainda" sai quando a onda fechar.
BORDA_LIDA = ("A borda é a cor do plástico que o Hefesto <b>leu do aparelho</b>: este controle "
              "está no cabo, e pelo cabo ele pergunta e o aparelho responde.")
#: A DICA NÃO CONFESSA ROADMAP — 30/08/2026, regra dela: *"informar na dica que
#: o produto não presta e não tá pronto é o fim dos tempos"*. Ela estava certa: a
#: pessoa que passa o mouse quer saber POR QUE a borda está cinza, não em que
#: onda do nosso plano a cor vai chegar. O código da sprint sai da tela e fica
#: aqui, onde é útil a quem programa. A frase passa a dizer o que É: a cor não
#: foi lida, e por isso a borda não a inventa.
BORDA_NEUTRA = ("A borda é <b>neutra</b> porque a cor deste controle <b>não foi lida</b>. "
                "Uma borda colorida aqui seria uma cor que ninguém leu — e o desenho "
                "continua na cor que o resto do Hefesto já conhece.")

LUZ_NO_CABO = ("Só funciona com o controle no rádio: a cura é derrubar a conexão Bluetooth "
               "para você apertar PS. Este controle está no cabo, onde a barra de luz não "
               "depende de reconexão nenhuma.")
LUZ_NO_RADIO = ("Derruba este controle do rádio para você apertar PS e a barra de luz voltar "
                "a obedecer. Enquanto ele espera o PS, o mesmo botão vira “Cancelar”.")

# A PALAVRA DA UNIDADE É **TURNO**, e não "fatia" nem "faixa"
# (`D-A-FATIA-DO-RADIO-VIRA-TURNO`, 28/08). Ela pediu "faixas"; a colisão é
# medida e está nesta MESMA aba, a poucos centímetros da régua: "faixa de 2,4
# GHz" aparece três vezes (o exame, o título da coluna dos vizinhos e a dica do
# imperativo), e a régua conta TEMPO — 625 µs por turno, `radio_da_mesa.py` —,
# não frequência. Vista a colisão, ela validou: *"a ideia é mostrar algo tipo
# porções, divisões, turnos funciona também."*
#
# SÓ A TELA TROCA. Em `src/` a palavra "fatia" aparece 75 vezes e a maioria é
# outro sentido — a fatia de TEMPO do laço do daemon (`daemon/connection.py`).
# Troca cega lá quebraria código não relacionado.
# AS DUAS FRASES DO MICROFONE MUDARAM DE CASA — 04/09/2026, e o `+16,3` que uma
# delas trazia DIGITADO virou derivado. Elas moram agora em
# `a08_conexoes._DICA_DO_MIC` (a metade física, que é fato de protocolo e
# continua verdadeira) mais `secao_controles.frase_da_capacidade_do_mic()` (o
# custo, que deriva as constantes do medidor).
#
# POR QUE O NÚMERO NÃO PODIA FICAR AQUI: os 16,3 conferiam com `radio_da_mesa`
# HOJE — eles são a segunda grafia, e no dia em que alguém remedir o A/B a
# janela estável acompanha e o HTML não. É a forma de defeito que
# `frase_da_capacidade_do_mic` foi escrita para impedir.
#
# E O `title` DESTE RESUMO DEIXOU DE SER DÍVIDA no mesmo dia: ele ganhou
# `data-campo="mic-dica"` com alvo `atributo`, então segue o transporte VIVO em
# vez de congelar o da cena.
MIC_LIGADO_DICA = (
    "Se o microfone deste controle existe. Desligado, nenhum programa o enxerga — nem o jogo, "
    "nem a chamada de voz. <b>Por onde</b> ele chega não é escolha: quem decide é o transporte, "
    "e a linha ao lado diz qual é.")
#: O `?` DO BLOCO DO MICROFONE, segunda metade — e ela deixou de DECIDIR em
#: 04/09/2026. A frase dizia *"Decide se o botão físico … cala só ele ou o
#: computador inteiro"*, e a tela oferecia a escolha por controle enquanto o
#: produto guarda UM valor por máquina. Agora ela DIZ.
#:
#: **A DOUTRINA É A DESTA MESMA ABA**, e está escrita na legenda dela: a
#: chavinha *"pelo cabo / pelo rádio"* saiu porque *"oferecia uma escolha que o
#: transporte já tinha feito"*. Aqui a escolha já tinha sido feita por ELA —
#: *"o botão do Controle sempre controla a interface"* (30/08) e *"o botão é pra
#: ligar o microfone e ele ser ouvido no canal específico dele"* (D-12, 04/09),
#: que é um ato só. Não há duas rotas com dois comportamentos a escolher.
BOTAO_DICA = (
    "O botão físico do microfone faz o mesmo que o desta tela: liga o microfone "
    "<b>e</b> o canal dele. O que ele cala é <b>um ajuste da máquina</b>, não "
    "deste controle — a linha ao lado diz qual está valendo.")

#: A MESMA COISA EM UMA LINHA, para o `title` da leitura. O `?` do bloco explica;
#: o hover da linha responde "o que é isto que estou lendo".
BOTAO_DICA_CURTA = (
    "O que o botão físico do microfone cala. É um ajuste da MÁQUINA, um só para "
    "todos os controles — o Hefesto o lê do serviço a cada tique.")

#: A DICA DO GESTO, e ela é a MESMA nos três estados de propósito.
#:
#: `title` não muda com CSS. A dica antiga dizia *"Abre este controle — e fecha
#: os outros"*, e no estado "Todos" ela mentia duas vezes: a linha já estava
#: aberta, e o que o clique faz ali é FECHAR as outras três. Esta frase é
#: verdadeira nos dois casos, porque descreve o RESULTADO e não o movimento.
SO_ESTE_DICA = ("Deixa só este controle aberto — os outros fecham.")


def teto_dica(c):
    """A frase do `?` do teto — desenho de bancada, REPINTADA pelo pacote.

    O `?` GANHOU ENDEREÇO em 01/09/2026 (`data-campo="teto-explica"`), e ele tem
    de ser pintado JUNTO com o `<select>`: a frase daqui diz *"este controle
    segue o global, que vale …"* a partir de `PERFIL_DA_MESA`, que é constante
    de bancada. Ligar só a caixa deixaria a tela dizendo "30% da força" no campo
    e "segue o global" na dica — uma contradição NOVA, introduzida por nós.

    O ALVO É `html`, e não o `texto` padrão: esta frase traz `<b>` e `<code>` no
    desenho dela, e o `textContent` do `escrever()` os escreveria como texto
    literal — a dica mostraria os próprios marcadores.

    A FRASE É DO PRODUTO — `gui.aba_conexoes.dica_do_teto`. Aqui ficou só a
    bancada: qual controle sobrepõe e qual perfil de mesa esta tela mostra.
    """
    return _aba_conexoes.dica_do_teto(_vibracao_da_bancada(c))


# ---------------------------------------------------------------------------
# O DESENHO DO CONTROLE SEGUE O APARELHO — a lei dela, 03/09/2026:
#
#     "os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
#      players com cada controle — tudo isso muda de acordo com o controle
#      identificado no canto superior. é white no p1, mas a borda de tudo é
#      cosmic red e os svgs não são os que o meu mapa cataloga. isso tá errado"
#
# O CSS do `.ds-mini` guardava a dívida e a receita: *"a cura certa é um alvo de
# ATRIBUTO no piloto"*. Ele existe desde 03/09 (`data-hef-alvo="atributo"` mais
# `data-hef-atributo`), e são estas duas funções que o alcançam.
#
# SÃO DUAS METADES, E UMA SÓ NÃO CURA NADA — está medido pela frente que fez o
# alvo: `monta._so_o_colorway` guarda na folha de CADA `<svg>` só as regras do
# modelo pedido (3.082 bytes dos 45.452 dos 28). Escrever `white` num desenho
# cuja folha só traz `cosmic-red` dá o MESMO cinza neutro (`rgb(58, 63, 75)`) de
# um desenho sem atributo nenhum — troca-se uma cor errada por um cinza.
#
# A SAÍDA ESCOLHIDA É A TABELA COMPARTILHADA, e não podar menos: o bloco das
# cores sai de dentro dos desenhos e vai UMA vez para a página. A aritmética que
# `_so_o_colorway` documenta continua de pé — ela existe para uma aba não
# carregar QUATRO cópias dos 28 modelos; uma cópia só é o que ela pede.
#
# E O QUE VIAJA É O `<defs id="cores-do-dualsense">` INTEIRO, não só o `<style>`.
# Isto foi MEDIDO e quase passou: OITO dos 28 modelos não têm hex nenhum no mapa
# dela — Chroma Teal, Ghost of Yōtei, Grey Camouflage… — e a folha os pinta com
# `url(#hachura-sem-hex)`, uma hachura; outros dois usam gradiente
# (`casca-god-of-war-20th`, `casca-spider-man-2`). São 68 referências a TRÊS
# `id`, e o `monta.svg()` prefixa todo `id` por controle. Uma folha solta,
# unprefixada, apontaria para `#hachura-sem-hex` enquanto os desenhos definiriam
# `#p1-hachura-sem-hex`: oito modelos ficariam SEM TINTA, e só na máquina de
# quem tivesse um deles. O `<defs>` é a unidade que o
# `scripts/gerar_cores_do_dualsense.py` escreve, e é a unidade que se move.
#
# ELE VAI DENTRO DE UM `<svg>` DE ZERO PIXEL porque `<pattern>` e
# `<linearGradient>` só existem dentro de um fragmento SVG. O `url(#…)` de um SVG
# inline resolve contra o DOCUMENTO, então os dois desenhos o alcançam de lá.
# ---------------------------------------------------------------------------
_CORES_NO_DESENHO = re.compile(
    r'\n?[ \t]*<defs id="[^"]*cores-do-dualsense">.*?</defs>', re.S)

#: A ÂNCORA do endereço. `monta.svg()` reescreve a tag de abertura para
#: `<svg data-colorway="…" class="…" …`, e é nela que os três atributos entram.
_ABRE_O_DESENHO = '<svg data-colorway="'


def _a_tabela_dos_28() -> str:
    """As 28 cores dela, lidas do desenho — a TABELA, publicada uma vez.

    Ela não é digitada aqui e não pode ser: o dono é
    `scripts/gerar_cores_do_dualsense.py`, que a escreve no `ds_limpo.svg` a
    partir de `docs/data/cores-do-dualsense.csv`. Uma segunda cópia envelheceria
    sozinha no dia em que ela mapear o vigésimo nono modelo.
    """
    achado = _CORES_NO_DESENHO.search(DS)
    if not achado:
        raise SystemExit(
            "ERRO em 08-conexoes: o `<defs id=\"cores-do-dualsense\">` sumiu do "
            "`ds_limpo.svg` — sem ele o desenho não tem como virar outro modelo, "
            "e o alvo de atributo escreveria um colorway que nada casa.")
    return achado.group(0).strip()


TABELA_DAS_CORES = (
    '  <svg width="0" height="0" aria-hidden="true" focusable="false"\n'
    '       style="position:absolute;width:0;height:0;overflow:hidden">\n'
    f'  {_a_tabela_dos_28()}\n'
    '  </svg>')


def desenho_do_controle(c, luz):
    """O desenho pequeno da linha, com ENDEREÇO e sem a folha podada.

    Os três atributos são o contrato do alvo novo, e o par alvo/parâmetro vem
    separado de propósito — é o que o alvo `classe` já faz com `data-hef-classe`
    e `data-hef-quando`; um `data-hef-alvo` composto quebraria toda comparação
    por igualdade que lê o alvo.

    O ALVO É `atributo` E NÃO `html`: trocar o `<svg>` inteiro foi tentado e
    reprovou na medição (31 pinturas em 31 tiques, tique de 4,24 para 13,56 ms,
    e 50 KB atravessando a ponte a cada meio segundo), porque o `innerHTML` que o
    navegador devolve de um SVG nunca volta igual ao que se escreveu. O atributo
    são vinte bytes e a comparação casa.
    """
    x = svg(c["pref"], c["cor"], classes="ds-svg ds-mini", luz=luz, lampadas=False)
    if _ABRE_O_DESENHO not in x:
        raise SystemExit(
            f"ERRO em 08-conexoes: o desenho do {c['pref']} não abre com "
            f"`{_ABRE_O_DESENHO}` — sem essa âncora o endereço da cor cairia no "
            "lugar errado, que é pior que não existir.")
    x = x.replace(_ABRE_O_DESENHO,
                  '<svg data-campo="desenho" data-hef-alvo="atributo" '
                  'data-hef-atributo="data-colorway" data-colorway="', 1)
    # A TABELA PODADA SAI. Ela é a escolha de UM modelo cravada no arquivo; a
    # dos 28 já vai na página, uma vez, por `TABELA_DAS_CORES`.
    #
    # E A AUSÊNCIA PARA A GERAÇÃO, como o `_tira_grupo` do `monta.py`: um `sub`
    # que não casa devolve o texto intacto e não avisa — a página sairia com as
    # DUAS tabelas, a podada por dentro e a dos 28 por fora, e a de dentro
    # venceria por vir depois. É a cicatriz da fita que morreu em silêncio.
    limpo, quantas = _CORES_NO_DESENHO.subn("", x)
    if quantas != 1:
        raise SystemExit(
            f"ERRO em 08-conexoes: o desenho do {c['pref']} trouxe {quantas} "
            f"tabelas de cor onde devia trazer uma — o `<defs>` das cores mudou "
            f"de forma, e a podada ficaria na página vencendo a dos 28.")
    return limpo


def linha_do_controle(c):
    """Um controle do acordeão: a linha fechada e o corpo que ela abre.

    Nada aqui é digitado por controle: a cor da borda sai do desenho, a cor da
    luz sai do produto, o rótulo sai da ordem dela, a máscara e a bateria saem
    da aba Controles, e o transporte decide o que a linha pode prometer.
    """
    # O LUGAR DE QUEM NÃO ESTÁ NA MESA — 31/08/2026, regra dela para toda página:
    # *"o espaço fica, mas o nome do canto muda: agora o p3 e o p4 será
    # P3 bolinha Desconectado, igual página gatilhos"*.
    #
    # ELE NÃO ABRE, E ISSO É ESTRUTURA, NÃO REGRA: a linha nasce sem `<label
    # for=...>`, e sem label não há o que marque o rádio que o CSS expande. Uma
    # regra que PROÍBA abrir alguém desfaz sem perceber; um lugar sem gatilho não
    # tem como abrir. É a mesma escolha da aba Controles, no ponto 2.5 da lista.
    #
    # E NADA DO RESUMO SOBRA: máscara, microfone e bateria são leituras do
    # aparelho, e não há aparelho. Um travessão em cada uma diria que a leitura
    # falhou; a ausência diz que o controle não está.
    # O `data-controle` FICA AQUI TAMBÉM — decisão dela, 03/09/2026: *"tem que
    # aparecer desligado enquanto não tem nenhum controle. A partir do momento
    # que tiver, ele aparece o controle devidamente conectado. Se isso não
    # ocorre com os 4 controles em cada aba, então temos que construir isso e
    # garantir isso."*
    #
    # SEM O ENDEREÇO, O LUGAR VAZIO É VAZIO SÓ PORQUE O DESENHO O DESENHOU
    # VAZIO. Medido no DOM vivo em 03/09: `[data-controle="p3"]` devolvia ZERO
    # elementos nesta aba, e o produto não tinha por onde escrever no cartão
    # quando o terceiro controle chegasse.
    if not c.get("conectado", True):
        return f'''          <div class="gc-item gc-{c["pref"]} fora" data-controle="{c["pref"]}">
            <div class="gc-cabeca">
              <span class="gc-nome" title="Nenhum controle neste lugar.">Player {c["jogador"]} <span class="pt">•</span> Desconectado</span>
            </div>
          </div>'''

    no_radio = c["via"] == "BT"
    luz = "#%02x%02x%02x" % player_slot_color(c["jogador"])
    # a borda só é pintada de quem foi LIDO — o resto fica com a neutra do CSS
    # A TINTA DA BARRA, e ela é do ELEMENTO — ver o comentário do `.gc-cor` no
    # CSS. Quem não foi lido nasce sem tinta nenhuma, e é a barra que o pacote
    # apaga com `transparent` quando a leitura não vier.
    tinta = "" if no_radio else f' style="color:{cor_da_zona(c["cor"])}"'
    barra = f'<i class="gc-cor" data-campo="plastico" data-hef-alvo="cor"{tinta}></i>'
    da_controles = DA_CONTROLES[c["pref"]]
    # só o CAMPO sai daqui: o "Vale …, do global" que ficava ao lado saiu da tela
    # (`D-O-SEM-TETO-SAI-DOS-DOIS-LUGARES`) e vive agora no `?` do campo.
    campo_teto = teto_que_vale(c)[0]
    # A LISTA E A SUA ORDEM SÃO DO PRODUTO — `gui.aba_conexoes.opcoes_do_teto`.
    # Montá-la aqui pela terceira vez é o que fazia a borda do gesto conferir o
    # clique contra literais em vez de contra a lista que a tela desenhou.
    opcoes_teto = list(_aba_conexoes.opcoes_do_teto())
    mic_dica = _pacote08.dica_do_microfone("BT" if no_radio else "USB")
    # O RESUMO DO MICROFONE GANHOU ENDEREÇO — 03/09/2026, e as duas metades
    # dele estavam mentindo na mesa dela ao mesmo tempo:
    #
    #   · o `<b>Ligado</b>` era palavra do desenho. Medido em 03/09 com a mesa
    #     dela: o `maquina.json` diz que a ponte deste controle está
    #     DESLIGADA, e a linha fechada dizia "Microfone Ligado". O endereço é o
    #     MESMO `mic-existe` do `<select>` do corpo, de propósito — o piloto
    #     distribui um valor por `data-campo` e cada elemento o veste como
    #     sabe: `texto` no `<b>`, `valor` no `<select>`. Dois endereços para o
    #     mesmo fato é como duas grafias começam.
    #   · o caminho ("pelo cabo · Placa do controle") vinha do transporte da
    #     CENA. Ver `_pacote08.caminho_do_microfone`, que agora é o dono único.
    #
    # O `title` FICA COMO ESTÁ, e é dívida declarada: ele é do transporte da
    # cena e não segue o vivo. O alvo é um por elemento, e o que ela LÊ sem
    # passar o mouse é o texto.
    # A TRAVA DO BOTÃO VIROU DADO — 03/09/2026. A classe `apagado` continua
    # nascendo do transporte da CENA (é o que ela vê ao abrir o arquivo), e o
    # `data-campo="luz-trava"` é o que deixa o produto reescrevê-la a cada
    # tique: `data-hef-quando="cabo"` acende a classe quando o pacote emitir
    # `cabo`, e a apaga quando emitir `radio`.
    #
    # E A DÍVIDA DO `title` FECHOU EM 04/09/2026. O que estava escrito aqui —
    # *"a dica continua a do desenho, e isso é dívida declarada … um segundo
    # campo para o `title` pede outro elemento"* — estava certo, e o outro
    # elemento é o `<i class="ltrava">` abaixo: ele fica com a CLASSE e o botão
    # fica com a DICA. O que a dica ganha não é só seguir o transporte: vêm
    # junto o AVISO DA MESA SUJA (quando outro programa segura nó de controle
    # agora, a cura não pega) e a RAZÃO do carimbo de nascimento — os dois com
    # dono no produto e zero leitor no HTML até hoje. Ver
    # `a08_conexoes.dica_da_luz`.
    trava = (f'<i class="ltrava{"" if no_radio else " on"}" data-campo="luz-trava" '
             f'data-hef-alvo="classe" '
             f'data-hef-quando="{_pacote08.LUZ_TRAVADA}"></i>')
    dica_luz = ('data-campo="luz-dica" data-hef-alvo="atributo" '
                'data-hef-atributo="title"')
    botao = (f'{trava}<button class="btn" data-gesto="luz-nao-acende" {dica_luz} '
             f'title="{LUZ_NO_RADIO}">A luz não acende</button>' if no_radio
             else f'{trava}<button class="btn apagado" data-gesto="luz-nao-acende" '
                  f'{dica_luz} title="{LUZ_NO_CABO}">A luz não acende</button>')
    return f'''          <div class="gc-item gc-{c["pref"]}" data-controle="{c["pref"]}">
            {barra}
            <div class="gc-cabeca">
              <label class="gc-abre" for="gc-{c["pref"]}" data-gesto="alvo"
                     title="{SO_ESTE_DICA} A fita do topo passa a apontar para ele.">
              <span class="gc-nome" data-campo="nome" data-hef-alvo="html">{rotulo(c)}</span>
              <span class="gc-resumo">
                <span title="{"A borda deste controle é a cor lida do aparelho." if not no_radio else "A cor deste controle não foi lida — a borda fica neutra."}">Vê como <b>{c["mascara"]}</b></span>
                <span data-campo="mic-dica" data-hef-alvo="atributo" data-hef-atributo="title" title="{mic_dica}">Microfone <b data-campo="mic-existe">Ligado</b>, <span data-campo="mic-caminho" data-hef-alvo="html">{caminho_do_mic(c)}</span></span>
                <span title="A bateria vem da aba Controles, que é quem a lê do aparelho.">Bateria <b data-campo="bateria">{da_controles["bat"]}%</b></span>
              </span>
              </label>
              <label class="gc-seta abre" for="gc-{c["pref"]}" data-gesto="alvo"
                     title="{SO_ESTE_DICA}">▾</label>
              <label class="gc-seta so" for="gc-{c["pref"]}" data-gesto="alvo"
                     title="{SO_ESTE_DICA}">só este</label>
              <label class="gc-seta fecha" for="gc-todos" data-gesto="todos"
                     title="Fecha — a fita volta para “Todos”, e os {len(CONECTADOS)} controles abrem juntos.">▴</label>
            </div>
            <div class="gc-corpo">
              {desenho_do_controle(c, luz)}
              <span class="gc-bloco">
                <span class="rot">{glifo("mic", ativo=True, tam=16)} Microfone e botões
                  <span class="ajuda">?<span class="dica">{MIC_LIGADO_DICA}<br><br>{BOTAO_DICA}</span></span></span>
                {sel(["Ligado", "Desligado"], "Ligado", gesto="mic-existe", campo="mic-existe", dica="Se o microfone deste controle existe. Desligado, nenhum programa o enxerga — nem o jogo, nem a chamada de voz.")}
                <span class="leitura" data-campo="mic-escopo" title="{BOTAO_DICA_CURTA}">{BOTAO_DO_MIC}</span>
              </span>
              <span class="gc-bloco barra">
                <span class="rot">{glifo("rumble_esquerdo", ativo=True, tam=16)} Teto da vibração
                  <span class="ajuda">?<span class="dica" data-campo="teto-explica" data-hef-alvo="html">{teto_dica(c)}</span></span></span>
                {sel(opcoes_teto, campo_teto, gesto="teto-da-vibracao", campo="teto-da-vibracao", dica="O teto da vibração deste controle. O global manda e o do controle sobrepõe — o “?” ao lado diz qual dos dois está valendo agora.")}
              </span>
              {botao}
            </div>
          </div>'''


# ---------------------------------------------------------------------------
# A RÉGUA DO RÁDIO — o desenho dela, com a mesa da BANCADA.
#
# O HTML sai de `pacotes.a08_conexoes.html_da_regua_do_radio`, que é o dono das
# duas versões: esta e a que o produto pinta a cada tique. Aqui só se monta a
# mesa da bancada na língua que ele lê — e é essa a fronteira que a
# `IDENTIDADE-VEM-DE-CIMA-01` desenha: a FORMA é de quem desenha, o DADO é de
# quem lê o aparelho.
#
# POR QUE A RÉGUA INTEIRA E NÃO CAMPO A CAMPO: o `title` de cada fatia nomeia o
# plástico ("Starlight Blue — 260,4 turnos de entrada"), e não há alvo de
# atributo no `escrever()` do piloto. Um `title` congelado só se cura com o
# bloco nascendo do produto.
# ---------------------------------------------------------------------------
def _do_desenho(c):
    """Um controle da bancada na língua da régua: a cor já resolvida em hex."""
    return {"jogador": c["jogador"], "nome": c["nome"], "via": c["via"],
            "plastico": cor_da_zona(c["cor"]), "mic": tem_mic_pelo_radio(c)}


def regua_do_radio():
    pistas = []
    for a in ADAPTADORES:
        # SÓ QUEM ESTÁ NA MESA OCUPA BANDA: um controle desconectado não gasta
        # turno de rádio, e desenhá-lo na pista afirmaria uma disputa que não
        # existe.
        dentro = [POR_PREF[p] for p in a["prefs"] if POR_PREF[p].get("conectado", True)]
        # AS VAGAS SÃO OS CONTROLES DA MESA QUE HOJE ESTÃO NO CABO — não um "+1"
        # imaginário. A pergunta que a régua responde deixou de ser "quantos
        # caberiam" e passou a ser "e se os meus quatro viessem para o rádio".
        vagas = [x for x in CONECTADOS if x["pref"] not in a["prefs"]]
        pistas.append({"nome": a["nome"], "dica": f'{a["modelo"]} — {a["onde"]}',
                       "dentro": [_do_desenho(c) for c in dentro],
                       "vagas": [_do_desenho(c) for c in vagas]})
    return _pacote08.html_da_regua_do_radio(
        pistas, [_do_desenho(c) for c in NO_RADIO],
        teto=TETO, sem_mic=CUSTO_SEM_MIC, com_mic=CUSTO_COM_MIC,
        num=num, palavra=palavra_da_ocupacao)


# ---------------------------------------------------------------------------
# As contas que o texto do exame cita — contadas, nunca digitadas.
# ---------------------------------------------------------------------------
POR_NOMEAR = [v for v in RADIOS_VIZINHOS if v[2]]
JA_NOMEADOS = [v for v in RADIOS_VIZINHOS if not v[2]]
TOTAL_NO_RADIO = sum(custo(c) for c in NO_RADIO)
TODOS_COM_MIC = len(CONECTADOS) * CUSTO_COM_MIC
#: "o Player 1 e o Player 4" — a lista escrita por extenso, do jeito que se lê.
JOGADORES_NO_CABO = " e o ".join(f"Player {c['jogador']}" for c in NO_CABO)

# ---------------------------------------------------------------------------
# O VEREDITO DO DESENHO — decisão D-16 dela, 04/09/2026.
#
# A CENA DA BANCADA, declarada uma vez: os estados das CINCO linhas do exame na
# ordem em que elas saem, e quantas ordens de serviço a coluna da direita mostra
# aberta. Ela existe para a linha de veredito não ser DIGITADA: com os estados e
# a contagem, quem escreve a frase é o dono (`ordens_da_mesa.cabecalho`) e quem
# decide a cor é o dono (`exame_da_mesa.veredito`) — os mesmos dois que o pacote
# chama na tela viva.
#
# ELA TAMBÉM É RÉGUA: mudar o estado de uma linha do exame lá embaixo sem mudar
# esta lista faz o `_exigir` do fim do arquivo reprovar, porque a cor do topo
# deixa de bater com a pior das cinco.
# ---------------------------------------------------------------------------
ESTADOS_DO_EXAME = ("certo", _ATENCAO, "certo", "nao_sei", "certo")

#: Quantas ordens de serviço a cena tem abertas — o card da coluna da direita.
ORDENS_ABERTAS = 1

_CABECALHO = _ordens_da_mesa.cabecalho(
    # `cabecalho` só conta o comprimento da sequência; o que há dentro dela não
    # é lido. A cena tem UMA ordem aberta, e é ela que dá a frase.
    ordens=[None] * ORDENS_ABERTAS,
    conferidas=sum(1 for e in ESTADOS_DO_EXAME if e != "nao_sei"),
    sem_resposta=sum(1 for e in ESTADOS_DO_EXAME if e == "nao_sei"),
    dispensadas=0,
)

#: A COR DO PIOR ACHADO, e ela sai do MESMO `veredito()` que a janela estável
#: usa. O estado do cabeçalho entra na lista como mais um item: `veredito()`
#: devolve o pior de todos, que é o que `secao_exame.o_mais_grave` faz com dois
#: — e aquele módulo não é importável fora da venv (puxa `structlog` por
#: `escritor_cru`), enquanto este gerador roda com o `python3` da pasta.
VEREDITO_DO_DESENHO = _exame_da_mesa.veredito([
    _exame_da_mesa.Item(chave=f"desenho-{i}", rotulo="", estado=e, porque="")
    for i, e in enumerate((*ESTADOS_DO_EXAME, _CABECALHO.estado))
])


def _plural(n, um, muitos):
    return um if n == 1 else muitos


# ---------------------------------------------------------------------------
# POR QUE TRÊS QUADROS, e o que cada decisão de 28/08 custou em altura.
#
# A conta de moldura não mudou: cada quadro custa 54px (28 do topo, 24 do
# padding do corpo, 2 de borda) e o miolo gasta 14 entre um e outro. Quatro
# quadros são 258px dos 508 úteis antes de qualquer conteúdo, e por isso o
# Desempenho continua sendo SEÇÃO do terceiro, e não um quarto quadro — o que
# também é o que ela pediu: *"embaixo e separado"*, dentro do "Rádio e
# adaptadores". Os turnos são POR ADAPTADOR, e o adaptador é a linha da tabela
# logo acima.
#
# O QUE ESTA LEVA MEXEU NA ALTURA, medido no Chrome:
#   – "Microfone e botões" saiu do quadro (86px com a margem da sub-seção) e os
#     campos dele desceram para dentro de cada controle;
#   – "O que só você sabe" saiu, e ele NÃO paga nada: a coluna media 110px de  # (noqa-acento: verbo medir, imperfeito)
#     conteúdo contra 150 da coluna do exame, que é quem manda na altura;
#   – o acordeão fecha três dos quatro, mas custa mais do que a grade 2×2 que
#     ele substitui: quatro linhas em coluna, e não duas fileiras de dois.
# O número final está na LEGENDA, com o que teria de sair para caber.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# OS NÚMEROS DA APERTADA, medidos no Chrome em 28/08 e usados na legenda. Ficam
# aqui, e não escritos na prosa, porque a prosa envelhece calada.
#
# A ORDEM DOS QUADROS MUDOU, e ela é o que devolveu o terceiro para a tela. Só
# os quadros ACIMA de um decidem quanto dele aparece: com "Está tudo certo?" e
# "Gestão de Controles" na frente somando 469px, sobravam 29 para o terceiro — a
# barra do título e nada mais. A conta é fria: para o terceiro mostrar os 64px
# que a régua exige (título + primeira linha), os dois da frente têm de somar no
# máximo 434. Não havia arranjo dos três em que "Está tudo certo?" viesse antes e
# a soma coubesse; há um em que ela vem depois.
# ---------------------------------------------------------------------------
ALTURA = 828      # o que a aba mede, de ponta a ponta (o padding do miolo incluso)
VISIVEL = 542     # o que o miolo mostra
UTIL = 508        # o orçamento de conteúdo (o miolo menos o padding dele)
ESCONDE = 286     # o que rola por dentro — eram 332 antes desta leva
ESCONDE_ANTES = 332
#: A altura de cada quadro. Os nomes dizem QUAL, e não a posição: a posição
#: mudou nesta leva, e um `Q1` teria passado a significar outro quadro sem que
#: nenhuma linha da legenda mudasse de texto.
Q_GESTAO, Q_EXAME, Q_RADIO = 219, 204, 343
Q_GESTAO_ANTES = 265         # a Gestão de Controles antes de virar lista
VISIVEL_3 = 75    # o que o terceiro quadro mostra hoje — a régua exige 64
VISIVEL_3_ANTES = 29
TETO_DOS_DOIS = 434  # o quanto os dois primeiros podem somar sem afogar o terceiro
DESEMPENHO = 145  # a seção que fica embaixo, separada, no terceiro quadro
INVENTARIO = 130  # as duas colunas do terceiro quadro, com os dois botões
TODOS = 339       # a Gestão de Controles com os quatro abertos — eram 409
TODOS_ANTES = 409
ESCONDE_TODOS = 406          # o que rola por dentro no estado "Todos" — eram 476
ESCONDE_TODOS_ANTES = 476
#: O token de altura de campo do esqueleto, LIDO do `topo.html`. Escrevê-lo aqui
#: seria o oitavo literal — e o oitavo literal desta tela já esteve errado pelo
#: dobro uma vez.
H_ESCOLHA = int(re.search(r"--h-escolha:(\d+)px",
                          (pathlib.Path(__file__).resolve().parent / "topo.html").read_text()).group(1))
ALT_TV = 1080     # a TV dela — a janela abre com 757 em todas as dez abas
UTIL_TV = 831     # o que o miolo teria numa janela dessa altura


# ===========================================================================
# AS DUAS POP-UPS DA MESA — `#mapear-entradas` e `#mapear-entrada-a-entrada`.
#
# ELAS NÃO SÃO TELA NOVA: são as DUAS JANELAS QUE JÁ RODAM, desenhadas no
# padrão do redesenho. A regra desta leva é uma só — *se a janela do produto
# não tem o gesto, a pop-up não o desenha*:
#
#   · `app/widgets/mapa_da_mesa.py`      -> "Mapear Entradas"
#   · `app/widgets/calibrar_entradas.py` -> "Mapear Entrada a Entrada"
#
# TODO TEXTO DE TELA SAI DO PRODUTO, LIDO POR AST — a mesma disciplina que os
# sete números do rádio já seguem neste arquivo, e pela mesma razão: uma frase
# digitada aqui vira a segunda versão dela no dia em que o produto a corrigir,
# e régua nenhuma desta casa compara HTML com Python. O que o AST não alcança
# (f-string, literal dentro de função) vai para o `_confere_no_produto`, que
# reprova quando a frase deixa de existir lá.
# ===========================================================================
MAPA = _constantes(
    R / "src/hefesto_dualsense4unix/app/widgets/mapa_da_mesa.py",
    {"EXPLICACAO", "ROTULO_APARELHOS", "ROTULO_TIRAR", "ROTULO_EXTENSAO",
     "ROTULO_NOVA_ENTRADA", "ROTULO_NOVA_FACE", "ROTULO_FECHAR", "ROTULO_VAZIA",
     "ROTULO_POR_EXTENSAO", "NOME_DA_FACE_EM_BRANCO", "ESPERA_O_APLICAR",
     "CONFISSAO_ABERTURA", "CONFISSAO", "_COLUNAS"})

CALIB = _constantes(
    R / "src/hefesto_dualsense4unix/app/widgets/calibrar_entradas.py",
    {"FACES", "PERGUNTA_SENTADA", "SEM_SAIR_DA_CADEIRA", "ROTULO_JA_CHEGA",
     "ROTULO_NAO_SEI", "ROTULO_NAO_ALCANCO", "FIM_DA_FASE_SENTADA",
     "CONVITE_EM_PE", "ROTULO_VOU_MOSTRAR", "ROTULO_DEIXAR_PARA_DEPOIS",
     "CONVITE_DO_ENCAIXE", "PROCURANDO", "SEGUNDOS_ATE_O_NO",
     "SEGUNDOS_ATE_A_VIBRACAO"})

#: As duas perguntas da sala, lidas de onde elas moram HOJE. Elas mudam-se para
#: a "Mapear Entradas" nesta pop-up (`aba08.py` já registra a razão na legenda:
#: *"lá elas preenchem um vazio real"*), e vêm com pergunta, dica e as três
#: opções literais — nada aqui é redação nova.
SALA = _constantes(
    R / "src/hefesto_dualsense4unix/app/actions/config/secao_mesa.py",
    {"_PERGUNTA_DA_ALTURA", "_DICA_DA_ALTURA", "_PERGUNTA_DA_VISADA",
     "_DICA_DA_VISADA"})


def _confere_no_produto(caminho, frases):
    """Reprova quando uma frase de tela deixa de existir no fonte do produto.

    O AST lê constante de módulo; ele não alcança literal dentro de função nem
    f-string. O veredito de cada entrada (`arranjo_da_mesa.julgar`) e a frase
    dos dois relógios (`calibrar_entradas.OS_DOIS_RELOGIOS`) são justamente
    isso. Sem esta conferência a tela ficaria com uma CÓPIA muda: o produto
    trocaria "vale evitar" por outra palavra e o mockup continuaria verde,
    mostrando à Vitória uma tela que o produto não produz mais.
    """
    fonte = pathlib.Path(caminho).read_text()
    faltam = [f for f in frases if f not in fonte]
    if faltam:
        raise SystemExit(f"ERRO: {pathlib.Path(caminho).name} não diz mais "
                         f"{faltam} — a pop-up copiava essa frase.")


#: O julgamento por entrada, palavra por palavra de `arranjo_da_mesa.julgar`.
#: Só os estados que ESTA janela produz: ela nunca calcula plano, então os três
#: do modo ideal (`chega`, `sai`, `fica`) não entram.
_JULGAR = R / "src/hefesto_dualsense4unix/integrations/arranjo_da_mesa.py"
V_OCUPADA = "ocupada"
V_INDISPONIVEL = "indisponível"
V_SERVE = "serve"
V_EVITAR = "vale evitar"
V_MELHOR = "melhor lugar"
P_TIRAR = "clique para tirar"
P_EXTENSOR = "o extensor está nela"
P_SERVE = "entrada direta, mas na altura da mesa"
P_MELHOR = "na ponta do extensor: a antena mais longe das outras"
P_COLADA = "colada no {tipo}, na entrada {n}"
_confere_no_produto(_JULGAR, [
    f'"{V_OCUPADA}", f"{{tipo}} — {P_TIRAR}"', f'"{V_INDISPONIVEL}"',
    f'"{P_EXTENSOR}"', f'Veredito("serve", "{V_SERVE}", "{P_SERVE}")',
    f'"{V_EVITAR}", colada', f'"{V_MELHOR}"', f'"{P_MELHOR}"',
    'f"colada no {vizinho.tipo}, na entrada {entrada.par}"',
])

#: Os dois relógios da calibração. Os NÚMEROS saem do produto por AST; a frase
#: é f-string e por isso vive aqui, com o portão acima guardando as duas pontas
#: dela contra uma reescrita silenciosa.
def _virgula(n):
    # O DONO ÚNICO É `app.fala_do_mapa.formata_pt_br` — 26/08/2026. Aqui havia
    # a conta reescrita, byte a byte igual à dele. A saída não muda; o que muda
    # é que no dia em que o arredondamento mudar, esta linha não fica para trás.
    from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br

    return formata_pt_br(n)


OS_DOIS_RELOGIOS = (
    f"A entrada aparece para mim em ~{_virgula(CALIB['SEGUNDOS_ATE_O_NO'])} s. "
    f"O controle só consegue vibrar por volta de "
    f"{_virgula(CALIB['SEGUNDOS_ATE_A_VIBRACAO'][0])} a "
    f"{_virgula(CALIB['SEGUNDOS_ATE_A_VIBRACAO'][1])} s — e essa demora é uma "
    "correção que o próprio Hefesto instala para ele não falhar. Não é você, e "
    "não é o seu cabo.")
_confere_no_produto(
    R / "src/hefesto_dualsense4unix/app/widgets/calibrar_entradas.py",
    ["A entrada aparece para mim em ~", "Não é você, e não é o "])


def ajuda(txt, largura=""):
    st = f' style="width:{largura}"' if largura else ""
    return f'<span class="ajuda">?<span class="dica"{st}>{txt}</span></span>'


# ---------------------------------------------------------------------------
# A CENA — o mesmo mundo que a aba já mostra, um passo antes e um passo depois.
#
# NADA AQUI É INVENTADO NUM SENTIDO E DERIVADO NOUTRO: as duas linhas da tabela
# de adaptadores desta aba (`ADAPTADORES`) e as duas frases do exame ("o
# adaptador Bluetooth na Entrada 3 e o receptor do teclado na Entrada 4 saem do
# mesmo controlador USB 3.0"; "a Entrada 9 é de um controlador que só ela usa")
# são o enunciado. A cena é o que TEM de ser verdade para as duas valerem.
#
# O RÓTULO DE UM APARELHO É `espécie · nome do kernel`, e o caminho fica à
# vista de propósito — `mapa_da_mesa.py:434-442`: os dois adaptadores desta
# bancada são o mesmo 2357:0604, e a espécie sozinha ofereceria dois itens
# idênticos. A cena repete a lição com DOIS teclados (`3-4` e `1-4`).
#
# "Aparelho de entrada" NÃO É PALPITE: o censo classifica pela interface 0
# (`censo_do_barramento._especie`), e `mapa_das_portas._classe_do_motor` diz com
# todas as letras que o DualSense por cabo é `03/00/00` — classe de entrada sem
# protocolo de arranque. Logo o censo o nomeia pela classe, "Aparelho de
# entrada", e o MOTOR fica sem classe para ele (`""`) — que é o que acende a
# confissão de espécie mais abaixo.
# ---------------------------------------------------------------------------
#: `(espécie, nome do kernel, entrada em que ela o pôs, o que é na mesa dela)`
CENSO = [
    ("Aparelho de entrada", "1-2", "1",   f'o P{CONECTADOS[0]["jogador"]} {CONECTADOS[0]["nome"]}, no {"cabo" if CONECTADOS[0]["via"] == "USB" else "rádio"}'),
    ("Mouse",               "1-3", "7",   "o receptor do mouse"),
    # O SEGUNDO APARELHO DE ENTRADA É O SEGUNDO CONECTADO, não o `MESA[3]` —
    # 01/09/2026. Ele citava *"o P4 White, no cabo"*, e o P4 está DESCONECTADO
    # desde que ela mandou a mesa ter dois: o tooltip anunciava, na entrada 2, um
    # aparelho que não está na bancada.
    #
    # É a mesma família do que já se curou hoje na Iluminação (o botão de player
    # dizia *"o Galactic Purple, que tem o 3 hoje"* de um controle fora da mesa)
    # e na Navegação (quem navega o PC saía da `MESA`). Toda frase que nomeia um
    # controle tem de sair de `CONECTADOS` — a `MESA` sabe dos quatro lugares, e
    # a TELA só pode falar dos que estão ocupados.
    ("Aparelho de entrada", "1-5", "2",   f'o P{CONECTADOS[1]["jogador"]} {CONECTADOS[1]["nome"]}, no {"cabo" if CONECTADOS[1]["via"] == "USB" else "rádio"}'),
    ("Bluetooth",           "3-3", "3",   f'o adaptador “{ADAPTADORES[0]["nome"]}”'
                                          f' — {ADAPTADORES[0]["modelo"]}'),
    ("Teclado",             "3-4", "4",   "o receptor do teclado que o exame desta aba cita"),
    ("Câmera",              "3-5", None,  "a webcam, plugada agora e ainda sem lugar"),
    ("Não identificado",    "4-1", "5",   "o kernel declinou de classificar (classe ff)"),
]

#: O que está na mão dela — o primeiro tempo do gesto de dois tempos. É o
#: adaptador que a ordem de serviço desta mesma aba manda mudar de lugar, e por
#: isso a pop-up mostra a ordem sendo cumprida em vez de uma tela em repouso.
ESCOLHIDO = "3-3"

#: As faces que ela desenhou, na ordem em que desenhou. Os números das entradas
#: são do GABINETE e não se repetem entre faces (`LogicaDoMapa.acrescentar_entrada`
#: dá sempre o menor inteiro que ainda não existe em face nenhuma).
FACES = [
    ("Frente do gabinete", ["1", "2"]),
    ("Traseira", ["3", "4", "5", "6", "7", "8", "9", "10"]),
]

#: A entrada por extensão: `10` ganhou uma filha `10a`, vazia. A existência do
#: extensor é DECLARAÇÃO dela — cabo passivo não tem descritor USB e nenhuma
#: leitura de `/sys` o distingue (`mapa_da_mesa.py:691-697`).
EXTENSAO = {"10": "10a"}

ONDE_ESTA = {no: em for _, no, em, _ in CENSO if em}
QUEM_ESTA = {em: (esp, no) for esp, no, em, _ in CENSO if em}


def _irmas():
    """As entradas de duas em duas, na ordem em que ela desenhou a face.

    É a `irmas_de` do produto (`mapa_das_portas`), e é ela que faz o juízo
    "colada no vizinho" existir. A filha por extensão NÃO tem irmã por desenho —
    o cabo de um metro a põe longe de todo mundo — e essa ausência não é lacuna.
    """
    par = {}
    for _, numeros in FACES:
        for i in range(0, len(numeros) - 1, 2):
            par[numeros[i]] = numeros[i + 1]
            par[numeros[i + 1]] = numeros[i]
    return par


PARES = _irmas()


def veredito(n, esticada=False):
    """O que `arranjo_da_mesa.julgar` diz desta entrada, com o Bluetooth na mão.

    A ordem das perguntas é a do produto, e ela importa: ocupada vence tudo,
    indisponível vem antes do juízo, e o juízo por classe é o último.
    """
    if n in QUEM_ESTA:
        return "cheia", V_OCUPADA, f"{QUEM_ESTA[n][0]} — {P_TIRAR}"
    if n in EXTENSAO:
        return "cheia", V_INDISPONIVEL, P_EXTENSOR
    vizinho = QUEM_ESTA.get(PARES.get(n, ""))
    #: `CLASSES_DE_RADIO` do motor = {bt, wifi, teclado, mouse}. Um receptor de
    #: teclado ou de mouse é rádio de 2,4 GHz tanto quanto o dongle Bluetooth —
    #: é por isso que a entrada colada nele "vale evitar".
    if vizinho and vizinho[0] in ("Bluetooth", "Teclado", "Mouse"):
        return "evite", V_EVITAR, P_COLADA.format(tipo=vizinho[0], n=PARES[n])
    if esticada:
        return "melhor", V_MELHOR, P_MELHOR
    return "serve", V_SERVE, P_SERVE


#: As lacunas que ESTA cena produz, na ordem em que o produto as declara.
#:
#: MEDIDO no produto, e as duas primeiras não têm como não estar:
#:   · `posicao`   — `mapa_das_portas.py:520-527` não é condicional: basta
#:                   existir uma face.
#:   · `velocidade`— esta janela nunca escreve `nos`; quem escreve é a outra
#:                   (`calibrar_entradas.py:743-746`). Logo TODA entrada sai
#:                   `usb=2`, e é por isso que nenhum plug desta tela é azul.
#:   · `especie`   — os dois DualSense por cabo saem sem classe no motor.
#: `par` NÃO entra: as duas faces têm número par de entradas.
#: `regiao` NÃO entra: as duas têm pelo menos uma entrada com aparelho.
LACUNAS = ["LACUNA_POSICAO", "LACUNA_VELOCIDADE", "LACUNA_ESPECIE"]

# ---------------------------------------------------------------------------
# UMA COLISÃO DE NOME QUE A POP-UP DESCOBRIU, E O QUE ELA CUSTA NO PRODUTO.
#
# A confissão da velocidade manda a pessoa a uma tela pelo nome: *"enquanto você
# não passar por «Calibrar as entradas», eu trato todas como pretas"*. Esse é o
# `TITULO_DA_JANELA` da outra janela — e o botão que a abre chama-se, desde
# 28/08, **{MAPEAR_UMA_A_UMA}** (`D-MAPEAR-ENTRADAS-E-NAO-PORTAS`). Deixar o
# nome velho aqui mandaria ela procurar um botão que não existe nesta aba.
#
# A tela mostra o nome CERTO; quem tem de mudar é o produto, e em TRÊS lugares
# (`mapa_da_mesa.CONFISSAO`, `calibrar_entradas.TITULO_DA_JANELA` e o
# `mapa_da_mesa.TITULO_DA_JANELA`, que diz "A minha mesa" onde o botão diz
# "{MAPEAR_ENTRADAS}"). O `assert` abaixo é o portão: no dia em que o produto
# corrigir, a troca deixa de casar e a geração PARA — em vez de a tela passar a
# corrigir em silêncio uma frase que já está certa.
# ---------------------------------------------------------------------------
NOME_VELHO_DA_CALIBRACAO = "Calibrar as entradas"
_alvo = MAPA["CONFISSAO"]["LACUNA_VELOCIDADE"]
if NOME_VELHO_DA_CALIBRACAO not in _alvo:
    raise SystemExit(
        f"ERRO: a confissão da velocidade não diz mais “{NOME_VELHO_DA_CALIBRACAO}”. "
        f"Se o produto já a chama de “{MAPEAR_UMA_A_UMA}”, apague esta troca.")
MAPA["CONFISSAO"]["LACUNA_VELOCIDADE"] = _alvo.replace(
    NOME_VELHO_DA_CALIBRACAO, MAPEAR_UMA_A_UMA)

# ---------------------------------------------------------------------------
# A CONFISSÃO SAIU DO CORPO E VIROU DICA — decisão dela, 29/08/2026.
#
# A conta que a comprou está no CSS do `.mm-conf-linha`; aqui fica o TEXTO, e
# ele continua derivado das mesmas constantes do produto — nada abaixo é
# redação nova. Ele passa a viver em DUAS superfícies de hover:
#   · `CONFISSAO_EM_DICA`  — na dica do `?` do `.tn-topo`, junto com o que já
#     estava lá (é o pedido literal dela), em HTML;
#   · `CONFISSAO_EM_TITLE` — no `title` da linha que ficou no corpo, em texto
#     puro, que é o que o hover nativo aceita.
#
# POR QUE NAS DUAS, E NÃO UMA APONTANDO PARA A OUTRA: uma dica que responde
# "olhe noutro lugar" cobra um segundo gesto e ensina menos que uma que
# responde. E repetir aqui não abre a porta que a regra da casa fecha — as
# duas saem da MESMA constante, logo não há como uma envelhecer sem a outra.
#
# O `html.escape` não é zelo vazio: depois da troca acima a confissão da
# velocidade carrega ASPAS RETAS em volta de “{MAPEAR_UMA_A_UMA}”, e aspa reta
# dentro de `title="…"` fecha o atributo no meio da frase.
# ---------------------------------------------------------------------------
_CONFISSAO_ITENS = [f"· {MAPA['CONFISSAO'][k]}" for k in LACUNAS]
CONFISSAO_EM_DICA = ("<b>" + html.escape(MAPA["CONFISSAO_ABERTURA"]) + "</b><br>"
                     + "<br>".join(html.escape(i) for i in _CONFISSAO_ITENS))
CONFISSAO_EM_TITLE = "&#10;".join(
    html.escape(t) for t in [MAPA["CONFISSAO_ABERTURA"], *_CONFISSAO_ITENS])

#: A CONTA, por extenso — e ela é o que a linha do corpo entrega DE GRAÇA, sem
#: hover nenhum. É dado derivado (`len(LACUNAS)`), não frase de tela: por isso
#: pode nascer aqui sem ferir a regra de que todo texto sai do produto.
#: O `raise` é portão: no dia em que a cena acender uma sexta lacuna, a
#: geração PARA em vez de a tela publicar uma conta que não bate.
#:
#: A TABELA MUDOU-SE PARA O PACOTE — 03/09/2026, pela mesma razão do
#: `caminho_do_mic`: a linha agora é REPINTADA com as lacunas da mesa dela, e
#: duas tabelas de números por extenso divergiriam no dia em que uma crescesse.
_POR_EXTENSO = _pacote08.PALAVRA_DA_CONTA
if len(LACUNAS) not in _POR_EXTENSO:
    raise SystemExit(f"ERRO: a cena tem {len(LACUNAS)} lacunas e esta tela só "
                     f"sabe dizer {sorted(_POR_EXTENSO)} por extenso.")

#: A linha que FICA no corpo, fora da `.moldura` — sempre à vista.
#:
#: OS TRÊS ENDEREÇOS SÃO DE 03/09/2026, e o defeito que eles fecham foi medido
#: na mesa dela no mesmo dia: esta linha dizia **"três coisas"** — a conta da
#: CENA — e o desenho dela tem **UMA** lacuna (`especie`). A `.mm-conf-linha`
#: mora FORA do bloco `.mm-faces` que o pacote troca inteiro, então nunca era
#: repintada; a dica listava as três da bancada. Uma confissão que confessa a
#: mais manda ela procurar o que o produto já sabe, e é tão falsa quanto uma
#: que cala.
#:
#:   · `confissao-nada`  no `<div>`, alvo `classe`: acende `sumido` quando o
#:     pacote emite `sim`, isto é, quando NÃO há o que confessar. É a regra da
#:     GTK — lá a linha não é desenhada quando `confissao_do_desenho` devolve
#:     vazio. O `data-hef-quando` compara por IGUALDADE de propósito: sem ele o
#:     alvo vira booleano e o sumiço acenderia justo quando há confissão;
#:   · `confissao-dica`  no `<span>`, alvo `atributo`/`title`: os itens da mesa
#:     dela, um por linha;
#:   · `confissao-conta` no `<b>`: a palavra por extenso.
CONFISSAO_NA_TELA = (
    f'<div class="mm-conf-linha" data-campo="confissao-nada" '
    f'data-hef-alvo="classe" data-hef-classe="sumido" data-hef-quando="sim">'
    f'<span data-campo="confissao-dica" data-hef-alvo="atributo" '
    f'data-hef-atributo="title" title="{CONFISSAO_EM_TITLE}">'
    f'{MAPA["CONFISSAO_ABERTURA"]} '
    f'<b data-campo="confissao-conta">{_POR_EXTENSO[len(LACUNAS)]}</b>.'
    f'</span></div>')

#: As três dicas de botão da janela do desenho — literais de dentro de função,
#: logo fora do alcance do AST. O portão abaixo é quem as segura.
# AS TRÊS GANHARAM NOME NO PRODUTO em 01/09/2026 e são LIDAS — eram uma
# terceira grafia, e o `_confere_no_produto` logo abaixo existia só para
# conferir que ela ainda batia com a do `mapa_da_mesa.py`. Um portão que compara
# duas cópias é a confissão de que há duas.
from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import (  # noqa: E402
    DICA_ENUMERA,
    DICA_EXTENSAO,
    DICA_JA_COLOCADO,
)
_MAPA_PY = R / "src/hefesto_dualsense4unix/app/widgets/mapa_da_mesa.py"
_confere_no_produto(_MAPA_PY, [
    "Você já colocou este aparelho na entrada {n}.",
    "O sistema enumera este aparelho como {c}.",
    "Foi você quem disse que há uma extensão aqui.",
    "botao.set_size_request(84, 56)",
])


def ap_botao(esp, no, em, quem):
    """Um aparelho da lista — o `Gtk.ToggleButton` de `_desenhar_aparelhos`.

    Fica na lista mesmo depois de colocado, e clicável: o produto só lhe
    acrescenta a dica de onde ele já está. Clicar no que já está ativo
    DESESCOLHE.
    """
    # SEM DICA quando não há lugar: o produto também não põe
    # (`mapa_da_mesa._desenhar_aparelhos` só chama `set_tooltip_text` sob `if onde:`).
    dica = DICA_JA_COLOCADO.format(n=em) if em else ""
    return (f'<button class="mm-ap{" on" if no == ESCOLHIDO else ""}" '
            f'data-gesto="escolher-aparelho" '
            f'title="{dica} · Na mesa: {quem}.">{esp}'
            f'<span class="pt">·</span><code>{no}</code></button>')


def quadrado(n, esticada=False):
    """Uma entrada — o botão de 84×56 px, com as suas até quatro linhas.

    A ordem é a do produto (`_botao_de_entrada`): número, corpo, "por extensão"
    e o veredito. O corpo é a espécie de quem está lá, ou `vazia`.
    """
    estado, texto, porque = veredito(n, esticada)
    dentro = QUEM_ESTA.get(n)
    corpo = dentro[0] if dentro else MAPA["ROTULO_VAZIA"]
    dizeres = []
    if esticada:
        dizeres.append(DICA_EXTENSAO)
    elif dentro:
        dizeres.append(DICA_ENUMERA.format(c=dentro[1]))
    dizeres.append(porque)
    linhas = [f'<span class="mm-n">{n}</span>',
              f'<span class="mm-c{"" if dentro else " mm-vazia"}">{corpo}</span>']
    if esticada:
        linhas.append(f'<span class="mm-ext">{MAPA["ROTULO_POR_EXTENSAO"]}</span>')
    linhas.append(f'<span class="mm-v">{texto}</span>')
    # `data-v` É O VOCABULÁRIO QUE ESTA TELA JÁ TINHA — a CSS pinta por ele
    # (`.mm-sq[data-v="cheia"]`), e o ouvinte do piloto já o capta. O
    # `data-gesto` entra AO LADO, e não no lugar: trocar um pelo outro apagaria
    # a cor do quadrado.
    return (f'<button class="mm-sq" data-v="{estado}" data-gesto="escolher-entrada" '
            f'title="{" ".join(dizeres)}">'
            + "".join(linhas) + "</button>")


def celula(n):
    """Uma entrada do gabinete, e só ela.

    A FILHA POR EXTENSÃO SAIU DAQUI — 31/08/2026, e é o começo do que ela pediu:
    *"até mesmo uma seção diferente pra hubs e onde ele tá conectado"*.

    Ela morava empilhada DENTRO do quadrado da mãe, e o preço estava na medida:
    a coluna do `10` ficava com dois quadrados de larguras diferentes (82 e 73px,
    por causa do recuo de 9px que marcava a filiação), e a face inteira deixava
    de ter colunas — medi **8 colunas distintas** numa grade de 7.

    A regra que ela protegia continua de pé: a traseira segue com as OITO
    entradas do metal (`mapa_da_mesa.py:667-675`). O hub não entrou na fileira
    dela — ganhou face própria, e lá ele pode dizer o que aqui não cabia: em que
    entrada está ligado.
    """
    return '<div class="mm-cel">' + quadrado(n) + "</div>"


#: DE QUAL FACE É CADA ENTRADA — para o hub poder dizer onde está ligado. Sai das
#: próprias `FACES`, nunca digitado: mover uma entrada de face aqui muda o texto
#: do hub junto, e não há um segundo lugar para esquecer.
FACE_DA_ENTRADA = {n: nome for nome, numeros in FACES for n in numeros}


def face_dos_hubs():
    """A terceira face: o que não é buraco do gabinete.

    Ela existe porque hub e entrada não são a mesma coisa, e a tela os desenhava
    iguais: um hub é um aparelho que VOCÊ pôs na mesa e que CARREGA entradas —
    o gabinete não sabe dele. Aqui ele diz de onde pendura.
    """
    if not EXTENSAO:
        return ""
    celulas = "".join(
        f'<div class="mm-cel">{quadrado(filha, esticada=True)}'
        f'<span class="mm-ligado">ligado na entrada <b>{mae}</b>'
        f' <span class="mudo">· {FACE_DA_ENTRADA[mae]}</span></span></div>'
        for mae, filha in EXTENSAO.items())
    return f'''            <div class="mm-face">
              <div class="mm-face-cab"><span class="mm-face-nome">Hubs e extensões</span>
                <button class="btn mini" data-gesto="novo-hub" title="Acrescenta um hub ou uma extensão à mesa e pergunta em que entrada ele está ligado. Cabo passivo não tem descritor USB: nenhuma leitura do sistema o enxerga, e por isso quem o declara é você.">Acrescentar hub</button></div>
              <div class="mm-grade mm-grade-hubs">{celulas}</div>
            </div>'''


#: O DESENHO É DO PRODUTO desde 01/09/2026 — `gui/aba_conexoes.html_do_mapa`.
#: Ele vivia aqui, e com ele vivia uma SEGUNDA CÓPIA do motor: a `veredito()`
#: logo acima reescrevia à mão o `arranjo_da_mesa.julgar`, com os cinco
#: vereditos digitados como constantes. Agora o gerador passa a CENA e o
#: produto desenha — o mesmo desenho que o piloto usa com o gabinete DELA.
#:
#: A `veredito()` daqui FICA, e é ela que este gerador injeta: o motor de
#: verdade precisa de uma `Bancada`, que precisa do censo do barramento — e um
#: gerador de mockup não pode ler o `/sys` de quem o roda, senão a página sai
#: diferente em cada máquina. A cópia deixou de ser a da TELA e passou a ser o
#: que ela sempre foi: a cena de bancada.
MAPA_DESENHADO = _aba_conexoes.html_do_mapa(
    [{"nome": nome, "portas": numeros} for nome, numeros in FACES],
    quem_esta=QUEM_ESTA,
    extensoes=EXTENSAO,
    veredito_de=veredito,
    rotulos={"vazia": MAPA["ROTULO_VAZIA"],
             "por_extensao": MAPA["ROTULO_POR_EXTENSAO"],
             "nova_entrada": MAPA["ROTULO_NOVA_ENTRADA"]},
    dicas={"esticada": DICA_EXTENSAO,
           "enumera": DICA_ENUMERA,
           "nova_entrada": _aba_conexoes.DICA_NOVA_ENTRADA,
           "novo_hub": _aba_conexoes.DICA_NOVO_HUB})


#: AS TRÊS RESPOSTAS DE CADA PERGUNTA DA SALA, com o **id do esquema** ao lado
#: do rótulo — os mesmos pares de `secao_mesa._declaracoes`. O rótulo é o que
#: ela lê; o id é o que vai ao `maquina.json` (`MesaDeclarada.altura_da_antena`
#: e `.linha_de_visada`), e é ele que o gesto manda no `machine.declare`.
#:
#: "NÃO SEI" É `""` AQUI, E VIRA `None` LÁ. O esquema é `Literal["acima",
#: "abaixo"] | None` com `extra="forbid"`: mandar a string `"nao_sei"` faria o
#: pydantic recusar o DOCUMENTO INTEIRO, e o sintoma na tela seria "não consegui
#: gravar" em vez de "valor inválido" — é o que `secao_mesa._valor_do_seletor`
#: (`:1498`) já resolve do mesmo jeito, e a razão está escrita lá.
RESPOSTAS_DA_ALTURA = (("acima", "Sim"), ("abaixo", "Não"), ("", "Não sei"))
RESPOSTAS_DA_VISADA = (("com_gente", "Sim"), ("livre", "Não"), ("", "Não sei"))
_confere_no_produto(
    R / "src/hefesto_dualsense4unix/app/actions/config/secao_mesa.py",
    ['("acima", "Sim")', '("abaixo", "Não")',
     '("com_gente", "Sim")', '("livre", "Não")', '("nao_sei", "Não sei")'])


def pergunta_da_sala(texto, dica, respostas, marcada, gesto):
    """Uma das duas perguntas que barramento nenhum responde.

    Pergunta, dica e as TRÊS opções são literais de `secao_mesa._declaracoes`.
    `Gtk.ComboBox` está proibido nesta casa (o cosmic-comp fecha o popup no
    clique, cosmic-epoch#2497) — no produto é um `SegmentedSelector`, e aqui é
    o `.seg`, que é o mesmo desenho.

    A DICA É HOVER DO RÓTULO, e não um `?`: no produto ela é
    `texto.set_tooltip_text(...)` sobre o próprio `Gtk.Label` da pergunta
    (`secao_mesa.py:650`). E tem de ser — ver o comentário do `.mm-sala` no CSS:
    dica dentro da `.moldura` é dica recortada.

    O QUE **NÃO** VEIO ANEXADO: o produto gruda a `moldura.QUANDO_VALE` no fim
    desta dica, porque a seção dele não tem onde mais dizê-la. Aqui a frase já
    está na tela, por extenso, três linhas abaixo (`ESPERA_O_APLICAR`) — repeti-la
    no hover seria a mesma frase duas vezes na mesma caixa.

    O ENDEREÇO DA PINTURA CHEGOU EM 03/09/2026 (`MIGRA-08-01`), e ele cura uma
    tela que MENTIA: o `maquina.json` desta bancada diz
    `linha_de_visada='com_gente'`, e os TRÊS botões da visada estavam apagados —
    a tela dizendo que ninguém respondeu uma pergunta respondida. O "Sim" da
    ALTURA acertava por coincidência do mockup, que é pior: um acerto que não
    vem de leitura erra no primeiro clique dela.

    SÃO DOIS ATRIBUTOS COM DOIS VOCABULÁRIOS, e os dois são do produto —
    `data-modo` é o que o GESTO manda (onde `""` vira `None` no
    `machine_declare`), `data-hef-quando` é o que a PINTURA compara (onde `""`
    quer dizer "alvo booleano" e acenderia os três juntos). A razão inteira está
    em `pacotes.a08_conexoes._ID_NAO_SEI`, que é o dono do `"nao_sei"` daqui.
    """
    botoes = "".join(
        f'<button class="{"on" if nome == marcada else ""}" '
        f'data-gesto="{gesto}" data-modo="{ident}" '
        f'data-campo="{gesto}" data-hef-alvo="classe" '
        f'data-hef-quando="{ident or _pacote08._ID_NAO_SEI}">{nome}</button>'
        for ident, nome in respostas)
    return f'''              <div class="mm-perg">
                <span class="mm-q" title="{dica}">{texto}</span>
                <div class="seg">{botoes}</div>
              </div>'''


TELA_MAPEAR = f'''
<div class="tela-nova" id="mapear-entradas">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit">{MAPEAR_ENTRADAS}</span>
      {ajuda(
        "O gesto tem <b>dois tempos</b>: clique no aparelho, depois na entrada em que ele "
        "está. Um aparelho fica em <b>um</b> lugar — pôr onde ele não estava o tira de onde "
        "estava, no mesmo gesto.<br><br>"
        "Enquanto há um aparelho escolhido, <b>todo quadrado publica o juízo</b> para "
        "<i>ele</i>: sem sujeito a pergunta “aqui serve?” não existe, e a tela cala.<br><br>"
        "As duas perguntas do fim <b>mudaram-se da aba para cá</b> em 28/08, e aqui elas "
        "preenchem um vazio real: esta janela não guardava um único fato que só você tem. "
        "<b>Sem resposta</b> não é o mesmo que <b>“Não sei”</b>.<br><br>"
        + CONFISSAO_EM_DICA)}
      <a class="tn-x" href="#" title="Fechar">×</a>
    </div>
    <div class="tn-corpo">
      <div class="tn-frase">{MAPA["EXPLICACAO"]}</div>
      <div class="moldura">
        <div class="mm-rot-linha"><span class="mm-rot" title="Tudo que o censo do barramento achou, menos os hubs-raiz. O hub de bancada FICA: o cabo dele ocupa uma entrada da traseira. O que já tem lugar continua na lista e continua clicável — é assim que você o move de uma entrada para outra.">{MAPA["ROTULO_APARELHOS"]}</span></div>
        <!-- O ENDEREÇO CHEGOU EM 03/09/2026 (`IDENTIDADE-VEM-DE-CIMA-01`). O
             pacote já trocava esta lista inteira desde 01/09, mas por SELETOR
             CSS, pela chave `blocos` — e um bloco sem `data-campo` é invisível
             para as duas réguas desta casa: os `title` do desenho ("o P1 Cosmic
             Red, no cabo") passavam por congelados sem que nada visse que o
             produto já os reescrevia. Com o endereço, a troca é a MESMA e as
             réguas a enxergam. -->
        <div class="mm-lista" data-campo="aparelhos" data-hef-alvo="html">
{chr(10).join("          " + ap_botao(*a) for a in CENSO)}
        </div>
        <!-- O RECIPIENTE DO MAPA — 01/09/2026. Ele existe para o piloto poder
             TROCAR o miolo inteiro: as faces e as entradas são as que ELA
             declarou, e o número delas muda. Um bloco cujo número de filhos
             muda com o dado não tem como ser pintado campo a campo — é a mesma
             razão da fita, que se troca inteira desde que a mesa passou a ter
             dois lugares vazios.
             SEM CSS PRÓPRIO de propósito: é um `<div>` de bloco, e as
             `.mm-face` dentro dele empilham como empilhavam. -->
        <div class="mm-faces">
{MAPA_DESENHADO}
        </div>

        <div class="mm-sala">
          <div class="mm-rot-linha"><span class="mm-rot" title="Estas duas mudaram-se da aba para cá em 28/08, e aqui elas preenchem um vazio real: a janela do desenho não guardava um único fato que só você tem. Sem resposta não é o mesmo que “Não sei”: enquanto você não responder, o Hefesto sabe que ninguém disse; “Não sei” é você dizendo que olhou e não sabe.">O que só você sabe</span></div>
{pergunta_da_sala(SALA["_PERGUNTA_DA_ALTURA"], SALA["_DICA_DA_ALTURA"],
                  RESPOSTAS_DA_ALTURA, "Sim", "sala-altura")}
{pergunta_da_sala(SALA["_PERGUNTA_DA_VISADA"], SALA["_DICA_DA_VISADA"],
                  RESPOSTAS_DA_VISADA, None, "sala-visada")}
        </div>
      </div>
      {CONFISSAO_NA_TELA}

      <div class="acoes mm-acoes">
        <button class="btn apagado" data-gesto="tirar-daqui" title="Acende quando você clica numa entrada que TEM aparelho. Ele escreve “sem aparelho” nessa entrada — a entrada continua no desenho, só fica vazia.">{MAPA["ROTULO_TIRAR"]}</button>
        <button class="btn apagado" data-gesto="nova-extensao" title="Acende quando você clica numa entrada cujo número é só dígito. Cria a filha dela — a 10 vira 10a, depois 10b. Não há neta.">{MAPA["ROTULO_EXTENSAO"]}</button>
        <span class="mm-nova"><input class="mm-campo" placeholder="{MAPA["NOME_DA_FACE_EM_BRANCO"]}" maxlength="16">
          <button class="btn" data-gesto="nova-face" title="Cria uma face com o nome que você escreveu, sem entrada nenhuma. Sem nome, não cria.">{MAPA["ROTULO_NOVA_FACE"]}</button></span>
      </div>
      <div class="tn-frase mm-aplicar">{MAPA["ESPERA_O_APLICAR"]}</div>
    </div>
    <div class="tn-rod mm-rod">
      <a class="btn" href="#">{MAPA["ROTULO_FECHAR"]}</a>
    </div>
  </div>
</div>
'''


# ---------------------------------------------------------------------------
# `#mapear-entrada-a-entrada` — a cerimônia de um toque por aparelho.
#
# TRÊS TELAS, e não uma: os três estados que a janela tem, ligados pelos
# PRÓPRIOS botões dela. Custa só HTML (`:target`, sem uma linha de script) e não
# mente sobre transição nenhuma — responder a última pergunta leva ao fim, e
# `[{ROTULO_VOU_MOSTRAR}]` é a única porta para a fase em pé.
#
# É O MESMO MUNDO DA OUTRA POP-UP, NO MESMO MOMENTO: a webcam acabou de ser
# plugada e é o único aparelho sem lugar, logo a fase sentada tem UMA pergunta.
# Por isso um clique numa face aqui leva de verdade ao fim — não é atalho de
# mockup, é o que o produto faz.
#
# O QUE **NÃO** VEIO DO MOCKUP APROVADO DE 25/08 (`docs/process/sprints/
# 2026-08-25-CALIBRAR-AS-ENTRADAS/mockup/calibrar-entradas.html`): ele é mais
# rico que o produto em seis pontos que a janela nunca ganhou — barra de
# progresso, [Próximo aparelho], [mudar o número], [Outro nome…], o recibo
# "gravado" e o laudo de quatro blocos. O carimbo dela cobre aquele DESENHO;
# esta pop-up desenha o CÓDIGO.
# ---------------------------------------------------------------------------
_CALIB_PY = R / "src/hefesto_dualsense4unix/app/widgets/calibrar_entradas.py"
PROGRESSO = "entrada {feitos} de {total}"
_confere_no_produto(_CALIB_PY, [
    '"entrada {feitos} de {total}"', 'botao.set_size_request(-1, 30)',
    'self.rotulo_contador.set_text("")',
])

#: O único aparelho sem lugar — logo, a única pergunta da fase sentada.
SEM_LUGAR = [(esp, no) for esp, no, em, _q in CENSO if not em]

#: Quantas vagas a fase em pé oferece. As do DESENHO saem da conta; as outras
#: são o que a própria tela avisa com todas as letras — *"o sistema me lista
#: mais entradas do que existem no seu gabinete"* —, e quantas são é dado de
#: CENA, do mesmo tipo que "Entrada 3" e "Sala" já são nesta aba.
VAGAS_NO_DESENHO = (sum(len(ns) for _n, ns in FACES) + len(EXTENSAO)
                    - len(ONDE_ESTA))
CONECTORES_QUE_NINGUEM_ALCANCA = 2
EM_PE_TOTAL = VAGAS_NO_DESENHO + CONECTORES_QUE_NINGUEM_ALCANCA

#: A peneira do jogo aberto, AMARRADA AO FOCO e não à janela estar aberta — a
#: posse do vocabulário do controle é tomada no `focus-in` e solta no
#: `focus-out` (`calibrar_entradas.py:865-866, 1113-1123`). Dizer "enquanto esta
#: janela estiver aberta" prometeria o que o produto não faz nem quando a
#: peneira existir.
#:
#: **ELA É ESPECIFICAÇÃO, E DEPENDE DA `ONDA-CONEXOES-10`**: hoje a peneira
#: `botoes_para_o_jogo` está escrita e NÃO TEM CHAMADOR — é lápide viva do
#: `portao_a_casa_sabe_e_o_produto_nao_faz.py:1162`. A frase já está no `title`
#: do botão desta aba desde 28/08; aqui ela ganha o lugar certo e o contorno
#: certo. Nenhum glifo de X/O/D-pad acompanha: `ao_payload_do_controle` também
#: não tem chamador, então hoje o botão não anda na tela E chega ao jogo.
#: **A FRASE SAIU DA TELA EM 29/08/2026, E ISSO É A REGRA DA CASA.** O mockup
#: mostra o AGORA; a peneira NÃO EXISTE hoje — `botoes_para_o_jogo` está escrita
#: e sem chamador, e a lápide do `portao_a_casa_sabe_e_o_produto_nao_faz.py:1162`
#: diz o contrário com todas as letras: *"confirmar uma entrada com o cabo na mão
#: dispara um pulo ou um tiro no jogo aberto atrás da janela"*.
#:
#: Declarar a pendência em COMENTÁRIO não basta: quem abre o mockup lê a TELA, e
#: a tela prometia. O requisito não se perde — ele já está no contrato do
#: redesenho (linhas 667 e 861) e é entrega da ONDA-CONEXOES-10. Quando a peneira
#: ganhar chamador, a frase volta, e volta com o texto abaixo, que continua sendo
#: o certo: ela fala de *janela na frente*, não de *janela aberta*, porque a posse
#: do vocabulário do controle é tomada no `focus-in` e solta no `focus-out`
#: (`calibrar_entradas.py:865-866, 1113-1123`).
PENEIRA_QUANDO_ELA_EXISTIR = (
    "Enquanto esta janela estiver na frente, o que você apertar no "
    "controle fica <b>aqui</b> — não chega ao jogo aberto atrás.")
PENEIRA = ""


def cerimonia(ident, pergunta, contador, quem, botoes, dica):
    return f'''
<div class="tela-nova" id="{ident}">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit">{MAPEAR_UMA_A_UMA}</span>
      {ajuda(dica)}
      <a class="tn-x" href="#" title="Fechar">×</a>
    </div>
    <div class="tn-corpo">
      {f'<div class="tn-frase">{PENEIRA}</div>' if PENEIRA else ""}
      <div class="moldura">
        <div class="ce-cartao">
          <span class="ce-perg">{pergunta}</span>
          <span class="ce-cont">{contador}</span>
          <span class="ce-quem">{quem}</span>
        </div>
        <div class="ce-botoes">{botoes}</div>
        <p class="ce-relogios">{OS_DOIS_RELOGIOS}</p>
      </div>
    </div>
    <div class="tn-rod">
      <a class="btn" href="#" title="Avança um passo sem gravar e sem cobrar depois. No fim e na fase em pé ele não tem efeito visível — e mesmo assim fica no mesmo lugar, em todos os passos.">{CALIB["ROTULO_NAO_SEI"]}</a>
      <a class="btn" href="#" title="Fecha a janela na hora, sem confirmação e sem resumo. Nada se perde: cada resposta já foi ao disco.">{CALIB["ROTULO_JA_CHEGA"]}</a>
    </div>
  </div>
</div>
'''


TELA_SENTADA = cerimonia(
    "mapear-entrada-a-entrada",
    CALIB["PERGUNTA_SENTADA"],
    PROGRESSO.format(feitos=1, total=len(SEM_LUGAR))
    + f' <span class="pt">·</span> {CALIB["SEM_SAIR_DA_CADEIRA"]}',
    f'{SEM_LUGAR[0][0]} <span class="pt">·</span> <code>{SEM_LUGAR[0][1]}</code>',
    "".join(
        f'<a class="btn{" foco" if i == 0 else ""}" '
        f'href="#mapear-entrada-a-entrada-fim" title="Cria uma entrada numerada '
        f'nova nesta face para este aparelho e para tudo que pende dele, e grava '
        f'no disco na hora — sem IPC, funciona com o Hefesto desligado.">{f}</a>'
        for i, f in enumerate(CALIB["FACES"])),
    "A pergunta é sobre a <b>entrada</b>, não sobre o aparelho: mesmo quando o kernel "
    "não diz o que é a coisa, você sabe em que buraco ela está.<br><br>"
    "O rótulo é <b>espécie · nome do kernel</b>. O caminho fica à vista porque é a única "
    "coisa que distingue dois aparelhos idênticos.<br><br>"
    "O <b>foco</b> já está em <b>{}</b>: não há live region alcançável no GTK 3, "
    "então mover o foco <i>é</i> o anúncio do passo novo.".format(CALIB["FACES"][0]))

TELA_FIM = cerimonia(
    "mapear-entrada-a-entrada-fim",
    CALIB["FIM_DA_FASE_SENTADA"],
    "",
    CALIB["CONVITE_EM_PE"],
    f'<a class="btn foco" href="#mapear-entrada-a-entrada-em-pe" title="Guarda a leitura '
    f'de agora como referência e entra na fase em pé. É a única porta para ela.">'
    f'{CALIB["ROTULO_VOU_MOSTRAR"]}</a>'
    f'<a class="btn" href="#" title="Fecha a janela. Mesmo destino do “{CALIB["ROTULO_JA_CHEGA"]}”.">'
    f'{CALIB["ROTULO_DEIXAR_PARA_DEPOIS"]}</a>',
    "É um <b>fim de verdade</b>: sem aviso de incompletude, sem selo de pendência, sem "
    "cartaz. O contador some, porque não há mais o que contar nesta fase.<br><br>"
    "Quem já tem lugar para tudo <b>abre a janela direto aqui</b>.")

TELA_EM_PE = cerimonia(
    "mapear-entrada-a-entrada-em-pe",
    CALIB["CONVITE_DO_ENCAIXE"],
    PROGRESSO.format(feitos=1, total=EM_PE_TOTAL),
    CALIB["PROCURANDO"],
    f'<a class="btn foco" href="#" title="Tira esta entrada da conta de vez: não vira '
    f'dívida, não vira aviso, e o Hefesto não volta a perguntar. Ela diminui o TOTAL do '
    f'contador, não o feito.">{CALIB["ROTULO_NAO_ALCANCO"]}</a>',
    "Aqui a face <b>não se pergunta</b>: toda entrada aprendida de pé é gravada em "
    "<b>{}</b>.<br><br>O total <b>encolhe</b> — ele é recalculado pela leitura de agora, "
    "e “{}” tira uma vaga da conta. Por isso não há barra de progresso: uma barra andaria "
    "para trás.".format(CALIB["FACES"][1], CALIB["ROTULO_NAO_ALCANCO"]))


MIOLO = f'''
    <!-- ======== A TABELA DAS CORES DELA, uma vez para a página inteira ========
         Os 28 modelos e as 10 zonas de `docs/data/cores-do-dualsense.csv`, com a
         hachura e os dois gradientes que oito deles usam — o
         `<defs id="cores-do-dualsense">` inteiro, lido do `ds_limpo.svg` por
         `_a_tabela_dos_28`. Ele morava DENTRO de cada desenho e vinha PODADO
         (só o modelo que o mockup escolheu), e uma tabela podada não tem como
         virar outro modelo: o alvo de atributo escreveria `white` e a casca
         continuaria caindo no cinza cru do desenho.
         O `<svg>` mede ZERO e não desenha nada — ele existe porque `<pattern>` e
         `<linearGradient>` só valem dentro de um fragmento SVG. Não muda um
         pixel do que ela aprovou. ======== -->
{TABELA_DAS_CORES}

    <!-- ======== 1. CHECK-UP — juízo à esquerda, conserto à direita ========
         SUBIU PARA PRIMEIRO E MUDOU DE NOME — 30/08/2026, pedido dela:
         *"a parte 'Está tudo certo' aparece como primeiro bloco na página e
         mudamos o nome pra Check-up"*. Faz sentido de leitura: quem abre a
         Conexões quer primeiro saber se há algo errado, e só depois a lista
         de quem está na mesa. E "Check-up" é substantivo — nomeia a seção;
         "Está tudo certo?" era pergunta, e título que pergunta faz a pessoa
         procurar a resposta em vez de ler o que está embaixo. ======== -->
    <div class="quadro">
      <!-- SÓ O CHECK-UP NASCE ABERTO — 30/08/2026, pedido dela: *"inicia as
           demais abas de gestão e rádio minimizadas"*. Faz sentido de uso: quem
           abre a Conexões quer primeiro saber se há algo errado; a lista da mesa
           e o inventário de rádios são consulta, não alerta. E resolve, de
           quebra, os 208px que o quadro de baixo perdia por não caber. -->
      <!-- ABRIR UMA MINIMIZA AS OUTRAS — 31/08/2026, pedido dela: *"abrir uma
           expansão minimiza a outra"*.

           `type="radio"` COM O MESMO `name`, e não JavaScript: é a gramática que
           esta casa já usa no interruptor da aba Jogar e nos três estados da
           página de calibração. O navegador é quem garante a exclusão — não há
           estado a sincronizar, e o mockup continua sem uma linha de script.

           O QUE ISSO TROCA, e é troca boa: com rádio não se fecha a última
           clicando nela de novo, então há SEMPRE uma seção aberta. Medido antes:
           com as três fechadas sobravam **428px** de vão até o rodapé, e com as
           três abertas a página passava **248px** do miolo e rolava. Os dois
           extremos deixam de existir.

           O CSS do esqueleto não precisou mudar: ele lê `input.abre:checked`,
           que vale igual para caixa e para rádio. -->
      <input class="abre" type="radio" name="cx8-secao" id="cx8-2" checked>
      <div class="quadro-topo">
        <label class="quadro-titulo" for="cx8-2">Check-up</label>
        <span class="ajuda">?<span class="dica">
          Um exame da <b>sala</b>: em que entradas os aparelhos estão, quanta energia elas
          dão, e quem mais está falando no rádio perto do seu adaptador.<br><br>
          É a resposta para "por que o controle no rádio engasga <b>aqui</b> e não engasga na
          casa de outra pessoa".<br><br>
          O exame <b>não muda nada sozinho</b>. Quando ele acha algo, aparece ao lado uma
          ordem de serviço dizendo <b>o que mover para onde</b>.<br><br>
          As duas perguntas que <b>só você</b> pode responder — a altura do dongle e se tem
          gente entre ele e o sofá — mudaram de lugar em 28/08: elas moram no
          <b>{MAPEAR_ENTRADAS}</b>, que é a janela onde você já declara a sala.
        </span></span>
        <!-- O CARIMBO GANHOU ENDEREÇO em 02/09/2026. Ele dizia "há 3 minutos"
             desde que o mockup nasceu, e nunca soube nada: nenhum pacote
             escrevia aqui, então a frase era a mesma com o exame recém-corrido
             e com a aba aberta desde ontem. A palavra da idade é do produto
             (`secao_exame.frase_de_quando`), e a moldura "Examinado …" é a
             deste desenho. -->
        <span class="conta" data-campo="examinado">Examinado há 3 minutos</span>
      </div>
      <div class="quadro-corpo">
        <!-- A LINHA DE VEREDITO — decisão D-16 dela, 04/09/2026:
             *"Uma linha de veredito no topo."*, *"Na cor do pior achado."*

             ELA FICA ACIMA DAS DUAS COLUNAS, e não dentro da do exame: a
             resposta vale para as duas — os achados à esquerda e a ordem de
             serviço à direita —, e pendurá-la em uma delas faria a pergunta
             *"está tudo certo?"* ser respondida por metade da seção.

             A FRASE E A COR NÃO SÃO DIGITADAS: saem de
             `ordens_da_mesa.cabecalho()` e de `exame_da_mesa.veredito()` sobre
             a cena declarada em `ESTADOS_DO_EXAME`, que são os mesmos dois
             donos que `a08_conexoes._veredito_do_exame` chama na tela viva. -->
{veredito_do_checkup(VEREDITO_DO_DESENHO, _CABECALHO.texto)}
        <div class="duas-colunas">

          <div class="lado-e">
            <div class="col-exame">
{exame("certo",
       f'As entradas dão energia para {"os" if len(NO_CABO) > 1 else "o"} {len(NO_CABO)} '
       f'{_plural(len(NO_CABO), "controle", "controles")} no cabo',
       "<b>O que eu vi:</b> as entradas em uso entregam 500 mA ou mais.<br><br><b>Por que "
       "importa:</b> entrada fraca faz o controle cair do cabo no meio da partida, e o sintoma "
       "parece defeito do controle.", linha=0)}
{exame(_ATENCAO, "Dois rádios da bancada estão em entradas vizinhas",
       "<b>O que eu vi:</b> o adaptador Bluetooth na <b>Entrada 3</b> e o receptor do teclado na "
       "<b>Entrada 4</b> saem do mesmo controlador USB 3.0.<br><br><b>O que fazer:</b> a ordem de "
       "serviço ao lado, e o <b>?</b> dela diz por que isso importa.", linha=1)}
{exame("certo",
       (f'Os {len(NO_CABO)} controles no cabo têm uma entrada cada um' if len(NO_CABO) > 1
        else 'O controle no cabo tem uma entrada só para ele'),
       f'<b>O que eu vi:</b> nenhum outro aparelho de dados divide o controlador USB das '
       f'entradas onde estão o {JOGADORES_NO_CABO}.', linha=2)}
{exame("nao_sei",
       f'{len(RADIOS_VIZINHOS)} rádios vizinhos ativos na faixa de 2,4 GHz',
       f'<b>O que eu vi:</b> {len(RADIOS_VIZINHOS)} fontes de rádio perto. {len(JA_NOMEADOS)} você '
       f'já nomeou; {len(POR_NOMEAR)} continuam por nomear, na tabela de '
       f'<b>Rádio e adaptadores</b>.<br><br>'
       f'<b>Por que importa:</b> {len(NO_RADIO)} dos seus {len(CONECTADOS)} controles falam nessa mesma '
       f'faixa. O Hefesto não consegue nomear o que o sistema não nomeia — mas com o nome ele sabe '
       f'o que dá para desligar e o que não dá.', linha=3)}
{exame("certo", "Nenhuma outra ordem de serviço pendente",
       "<b>O que eu vi:</b> só o conselho das entradas vizinhas está aberto. Ordens que você mandou "
       f"ignorar não contam aqui — elas voltam em <b>{VER_IGNORADAS}</b>.", linha=4)}
            </div>
          </div>

          <div class="lado-d">
            <div class="col-ordem" data-campo="{CAMPO_DA_ORDEM}" data-hef-alvo="html">
            <div class="ordem">
              <div class="faca">Mova o adaptador Bluetooth da Entrada 3 para a Entrada 9
                <span class="ajuda">?<span class="dica" style="left:auto;right:22px">
                  <b>O que eu vi:</b> o adaptador Bluetooth está na <b>Entrada 3</b> e o
                  receptor do teclado na <b>Entrada 4</b> — as duas saem do mesmo controlador
                  USB 3.0.<br><br>
                  <b>Por que importa:</b> USB 3.0 gera ruído exatamente na faixa de 2,4 GHz,
                  que é a faixa do Bluetooth. É a causa mais comum de engasgo no rádio, e não
                  aparece em log nenhum.
                </span></span>
              </div>
              <div class="receita">
                <span class="caixa" title="Entrada 3 — traseira do gabinete, USB 3.0. É a que divide o controlador com o receptor do teclado.">Entrada 3 <span class="pt">•</span> USB 3.0</span>
                <span class="seta">→</span>
                <span class="caixa alvo" title="Entrada 9 — traseira do gabinete, USB 2.0, num controlador que só ela usa.">Entrada 9 <span class="pt">•</span> USB 2.0</span>
              </div>
              <div class="ganho"><span>Ganho esperado:</span> sai do controlador do teclado e do
                ruído do USB 3.0 — e {"são " + str(len(NO_RADIO)) + " controles" if len(NO_RADIO) != 1
                else "é 1 controle"} dependendo desse rádio.</div>
            </div>
            </div>
          </div>

        </div>

        <!-- OS QUATRO BOTÕES SAÍRAM — 31/08/2026, e cada um por um motivo dela.

             *"não faz sentido termos o examinar e o reexaminar"*: os dois faziam
             a MESMA coisa — refazer o exame. `Já movi — reexaminar` só prometia
             comparar o antes com o depois, e essa comparação não estava desenhada
             em lugar nenhum. Sobrou um, e ele desceu para a seção que fala das
             entradas, como ela mandou.

             `Ignorar` virou glifo em cada linha do exame (ver `exame()`), que é
             onde o gesto tem sujeito. E `{VER_IGNORADAS}` saiu com ele.

             O QUE FICA EM ABERTO, e é dela: sem aquele botão, **não há hoje por
             onde reabrir uma ordem ignorada**. O desenho precisa dizer para onde
             a linha ignorada vai — apagada na própria lista é o caminho mais
             curto, e é decisão dela. -->
      </div>
    </div>

    <!-- ======== 2. GESTÃO DE CONTROLES — acordeão, um por controle ligado ======== -->
    <div class="quadro">
      <input class="abre" type="radio" name="cx8-secao" id="cx8-1">
      <div class="quadro-topo">
        <label class="quadro-titulo" for="cx8-1">Gestão de Controles</label>
        <span class="ajuda">?<span class="dica">
          Uma linha por controle <b>ligado</b>, e só eles. O que a <b>fita do topo</b> aponta vem
          aberto; clicar em outro abre ele e fecha os demais, e a fita acompanha. Clicar no que
          já está aberto volta para <b>Todos</b>, com os {len(CONECTADOS)} abertos.<br><br>
          <b>A linha fechada</b> diz quem é o controle e resume o que importa: o que o jogo
          <b>vê como</b> (a máscara, que se escolhe na aba <b>Jogar</b>), o <b>microfone</b> e a
          <b>bateria</b>. Máscara e bateria são leitura aqui — quem as governa é outra aba.<br><br>
          <b>A borda</b> é a cor do plástico que o Hefesto <b>leu do aparelho</b>. Quando a
          leitura não aconteceu, a borda fica <b>neutra</b> — porque uma borda colorida seria
          uma cor que ninguém leu. <b>O desenho segue a mesma leitura</b>: ele é o modelo que
          o mapa dela cataloga para aquele controle, e sem leitura fica cinza junto com a
          borda. <b>A barra de luz</b> não é a cor do plástico: é a cor canônica do
          <i>jogador</i> (<code>core/led_control.player_slot_color</code>).<br><br>
          <b>O microfone segue o transporte</b>, e isso não é escolha: pelo cabo ele vem pela
          placa de áudio do próprio aparelho; pelo rádio, pela ponte do Hefesto. As
          {num(CUSTO_DO_MIC)} turnos que ele custa no rádio são <b>consequência</b>, e aparecem
          na régua de Desempenho.
        </span></span>
        <span class="conta" data-campo="conta-gestao" data-hef-alvo="html">{CONTA_DA_GESTAO}</span>
      </div>
      <div class="quadro-corpo">
        <input type="radio" name="gc" id="gc-todos" class="gc-r">
{chr(10).join(f"""        <input type="radio" name="gc" id="gc-{c["pref"]}" class="gc-r"{" checked" if c["alvo"] else ""}>"""
              for c in MESA)}
        <div class="gc">
{chr(10).join(linha_do_controle(c) for c in MESA)}
        </div>
      </div>
    </div>

    <!-- ======== 3. RÁDIO E ADAPTADORES — o inventário e, embaixo e separado,
         o Desempenho. ======== -->
    <div class="quadro">
      <input class="abre" type="radio" name="cx8-secao" id="cx8-3">
      <div class="quadro-topo">
        <label class="quadro-titulo" for="cx8-3">Rádio e Adaptadores</label>
        <span class="ajuda">?<span class="dica">
          <b>{MAPEAR_ENTRADAS}</b> abre o desenho do seu gabinete e numera as entradas —
          depois disso o Hefesto para de dizer "porta 3-2.1" e passa a dizer "Entrada 9". É lá
          que ficam, desde 28/08, as duas perguntas que <b>só você</b> pode responder: se o
          dongle fica acima da cabeça de quem joga sentado, e se tem gente entre ele e o
          sofá.<br><br>
          <b>{MAPEAR_UMA_A_UMA}</b> é um toque por aparelho: você pluga, ele aprende.
          Enquanto isso corre, o que você aperta não vaza para o jogo aberto.<br><br>
          Os <b>rádios vizinhos</b> são tudo que fala em 2,4 GHz perto do seu adaptador. O
          sistema entrega o nome cru; quem sabe o que é, é você.
        </span></span>
        <a class="porta" href="mapa-das-portas.html" title="Abre o mapa das portas — o banco de provas deste quadro: as entradas do seu gabinete, os arranjos possíveis com o porquê de cada um, e a conta das {num(TETO)} fatias por adaptador. É o desenho do motor que já roda em integrations/arranjo_da_mesa.py.">Banco de provas: o mapa das portas&nbsp;↗</a>
      </div>
      <div class="quadro-corpo">
        <div class="duas-colunas">

          <div class="lado-e">
            <div class="linha-rot"><b style="color:var(--texto-suave)">Adaptadores Bluetooth</b></div>
            <!-- A TABELA GANHOU ENDEREÇO — 04/09/2026, e ela era a peça mais
                 lida desta aba sendo CENÁRIO. As duas linhas abaixo ("Sala /
                 TP-Link UB500 / Entrada 3" e "Sem nome / Intel AX211 /
                 Interno") são de uma bancada de exemplo; a mesa desta casa tem
                 TRÊS adaptadores, os três `2357:0604`, e o BlueZ dá a cada um o
                 nome que ela escreveu.

                 O BLOCO É TROCADO INTEIRO, com o `<tr>` do cabeçalho junto, e é
                 a mesma razão do `.mm-faces` e da régua do rádio: quantas
                 linhas existem é o que a máquina dela responde, e não há
                 endereço para uma `<tr>` que ainda não nasceu. Deixar o
                 cabeçalho fora obrigaria a pintura a conhecer a estrutura do
                 `<table>` do desenho.

                 AS TRÊS COLUNAS TÊM TRÊS DONOS NO PRODUTO, e nenhum deles é
                 este arquivo — ver `a08_conexoes._html_dos_adaptadores`. -->
            <table class="tab" data-campo="adaptadores-tabela" data-hef-alvo="html">
              <tr><th>Nome</th><th>Adaptador</th><th>Onde está</th></tr>
{chr(10).join(f"""              <tr><td{' class="mudo"' if a["nome"] == SEM_NOME else ""}><span class="renomeia" contenteditable="true" title="{RENOMEAR_DICA}">{a["nome"]}</span></td>
                  <td class="mudo">{a["modelo"]}</td>
                  <td>{a["onde"]} <span class="mudo">· {a["detalhe"]}</span></td></tr>"""
                  for a in ADAPTADORES)}
            </table>
            <div class="acoes empurra">
              <a class="btn" href="#mapear-entradas" title="Abre o desenho do seu gabinete e numera as entradas. É lá que ficam as duas perguntas que só você pode responder: a altura do dongle e se tem gente entre ele e o sofá.">{MAPEAR_ENTRADAS}</a>
              <button class="btn" data-gesto="examinar-portas" title="Refaz o exame das entradas — energia e rádio — e repinta os selos, as linhas e as ordens de serviço do Check-up.">{EXAMINAR_PORTAS}</button>
            </div>
          </div>

          <div class="lado-d">
            <div class="linha-rot"><b style="color:var(--texto-suave)">Outros rádios na faixa de 2,4 GHz</b></div>
            <div class="vizinhos">
{chr(10).join(viz_bloco(*v, linha=i) for i, v in enumerate(RADIOS_VIZINHOS))}
            </div>
            <div class="acoes empurra">
              <a class="btn" href="#mapear-entrada-a-entrada" title="Um toque por aparelho e o Hefesto aprende em que entrada cada um está.">{MAPEAR_UMA_A_UMA}</a>
            </div>
          </div>

        </div>

        <!-- ---- Desempenho: embaixo e separado, como ela pediu. ---- -->
        <div class="sub-secao">
          <div class="capa">
            <span class="rot"><b style="color:var(--texto-suave)">Desempenho</b>
              <span class="pt">•</span> O rádio de cada adaptador, em turnos</span>
            <span class="ajuda">?<span class="dica">
              O rádio Bluetooth de cada adaptador tem <b>{num(TETO)} turnos</b> de tempo para dividir
          entre tudo que fala nele. Cada controle come <b>{num(CUSTO_SEM_MIC)}</b>; com o
          microfone pelo rádio, <b>{num(CUSTO_COM_MIC)}</b> — {num(CUSTO_DO_MIC)} a mais.<br><br>
          Hoje <b>{len(NO_RADIO)} dos {len(MESA)}</b> controles estão no rádio:
          <b>{num(TOTAL_NO_RADIO)}</b>. As <b>vagas tracejadas</b> são os {len(NO_CABO)} que estão
          no cabo — se os {len(MESA)} viessem para o mesmo adaptador, seriam
          <b>{num(TODOS_COM_MIC)} das {num(TETO)}</b>. O microfone segue o transporte, então isso
          é o preço de quem vem para o rádio — e ele está aqui para você ver.<br><br>
          <b>De onde vêm os números:</b> os {num(TETO)} turnos são especificação do Bluetooth
          Classic (625 µs cada) e <b>nunca foram medidas aqui</b>; os {num(CUSTO_SEM_MIC)} e os
          {num(CUSTO_COM_MIC)} são o A/B desta bancada de 25/07/2026, com <b>um</b> controle — a
          soma de {len(MESA)} é derivada, e o maior ensaio de rádio desta casa foi de dois. Os
          quatro moram em <code>integrations/radio_da_mesa.py</code>, e esta tela os lê de
          lá.<br><br>
              <b>O teto da vibração não mora mais aqui:</b> o dropdown dos três perfis mudou-se
              para a aba <b>{ABA_DO_TETO_GLOBAL}</b>, onde se chama <b>{CASA_DO_TETO_GLOBAL}</b> —
              ele decide o que custa <b>bateria</b>, e esta régua mede o <b>rádio</b>. Cada
              controle continua podendo sobrepô-lo na linha dele, na <b>Gestão de Controles</b>.
            </span></span>
          </div>

        <!-- A RÉGUA INTEIRA TEM ENDEREÇO — 03/09/2026, `IDENTIDADE-VEM-DE-CIMA-01`.
             O `title` de cada fatia nomeia o plástico ("Starlight Blue — 260,4
             turnos de entrada") e não há alvo de ATRIBUTO no `escrever()` do
             piloto: um `title` congelado só se cura com o bloco nascendo do
             produto. Quantos adaptadores, quantos controles em cada um e
             quantas vagas mudam com a mesa dela — é a mesma razão da fita e do
             mapa do gabinete. -->
        <div class="regua-do-radio" data-campo="regua-do-radio" data-hef-alvo="html">
{regua_do_radio()}
        </div>
        </div>
      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>As duas janelas da mesa entraram na tela — e o que elas NÃO fazem</h2>
  <ul>
    <li><b>Os dois botões abrem agora, e o que abre não é tela nova.</b> <b>{MAPEAR_ENTRADAS}</b> é a janela <code>mapa_da_mesa.py</code> e <b>{MAPEAR_UMA_A_UMA}</b> é a <code>calibrar_entradas.py</code>, as duas já rodando. <b>Todo texto delas sai do produto, lido por AST</b> — a mesma disciplina dos sete números do rádio. O que o AST não alcança (o veredito de cada entrada, os dois relógios, as três dicas de botão) tem portão: a geração <b>para</b> se a frase deixar de existir no fonte.</li>
    <li><b>A cena é a SUA mesa, e é a ordem de serviço desta aba sendo cumprida.</b> O aparelho na mão é o adaptador <b>“{ADAPTADORES[0]["nome"]}”</b>, que o exame manda tirar da <b>Entrada 3</b> — e com ele escolhido cada quadrado publica o juízo <i>para ele</i>. Os cinco estados da tela são os cinco que a janela sabe produzir: <b>ocupada</b>, <b>indisponível</b>, <b>serve</b>, <b>vale evitar</b> e <b>melhor lugar</b>. Os três do modo ideal (<i>chega</i>, <i>sai</i>, <i>fica</i>) <b>não entram</b>: vêm do plano, e esta janela não calcula plano nenhum.</li>
    <li><b>Nenhum plug é azul, e a própria tela diz por quê.</b> A velocidade vem dos nós declarados, e quem os escreve é a OUTRA janela — logo toda entrada desenhada aqui sai <code>usb=2</code>. Pintar azul contradiria a confissão três blocos abaixo. <b>Mas repare a tensão</b>: o exame desta aba afirma que a Entrada 3 é <b>USB 3.0</b> e a 9 é <b>2.0</b>. As duas telas são honestas cada uma no seu canto, e o produto ainda não junta o que já sabe.</li>
    <li><b>Um nome não batia, e a tela corrigiu: a confissão mandava você a “Calibrar as entradas”.</b> Esse é o título da outra janela no código; o botão desta aba chama-se <b>{MAPEAR_UMA_A_UMA}</b> desde 28/08. A frase da tela já diz o nome certo — <b>quem falta corrigir é o produto</b>, e em três lugares: a confissão, o título da janela de calibrar, e o <code>TITULO_DA_JANELA</code> do desenho, que ainda diz <i>“A minha mesa”</i> onde o botão diz <b>{MAPEAR_ENTRADAS}</b>.</li>
    <li><b>As duas perguntas da sala chegaram, e vieram inteiras</b> — pergunta, dica e as três opções, literais de onde moravam. A da altura está respondida e a da visada não, de propósito: <b>sem resposta não é “Não sei”</b>, e a tela precisa mostrar os dois. <b>O preço, escrito:</b> elas gravam sob <code>mesa</code> e o desenho grava sob <code>mapa</code> — chaves com disciplinas diferentes (substituição num, fusão no outro). É trabalho de código, não de desenho, e a sprint que as implementar tem de saber disto.</li>
    <li><b>A cerimônia são TRÊS telas, ligadas pelos próprios botões dela</b>: a pergunta sentada, o fim da parte sem levantar, e a fase em pé. Custa só HTML e não mente sobre transição nenhuma — a webcam é o único aparelho sem lugar, então responder <i>aquela</i> pergunta leva mesmo ao fim.</li>
    <li><b>A frase do jogo aberto está amarrada ao FOCO, e ela é ESPECIFICAÇÃO.</b> A tela diz <i>“enquanto esta janela estiver na frente”</i>, e não “enquanto estiver aberta”, porque é no foco que a janela toma o controle. <b>Hoje o produto não faz isso</b>: a peneira está escrita e não tem quem a chame — é lápide viva do portão da casa. A frase depende da <code>ONDA-CONEXOES-10</code>. Por isso também <b>nenhum glifo de X/O/D-pad</b> acompanha: hoje o botão não anda na janela <i>e</i> chega ao jogo.</li>
  </ul>

  <h2>O que eu desenhei de cabeça, e por que — derrube qualquer um numa frase</h2>
  <ul>
    <li><b>A lista de aparelhos ficou EM CIMA, e no produto ela é a coluna da esquerda.</b> A conta é fria: o quadrado do produto tem <b>84&nbsp;px</b> e a fileira tem <b>sete colunas fixas</b> — 7×84 mais os vãos pedem <b>618&nbsp;px</b>, e a caixa oferece <b>624</b> por dentro. Lado a lado com uma coluna de lista, o quadrado cairia para ~56&nbsp;px e as linhas de texto dele parariam de caber. Empilhada, a fileira do produto cabe inteira.</li>
    <li><b>Os dois botões de ação nascem APAGADOS, e é o estado certo desta cena.</b> Eles só acendem com uma entrada em foco, e a janela <b>não tem realce nenhum de foco</b> — só os dois botões contam a história. Desenhá-los acesos seria desenhar um estado que ninguém consegue ver. As dicas dizem quando cada um acende. <b>Isto é defeito do produto</b>, não escolha de desenho.</li>
    <li><b>O quadrado cresce em altura quando o texto pede</b>, e “Aparelho de entrada” pede. O <code>84×56</code> do produto é <i>mínimo</i>, não teto — em GTK ele cresce igual.</li>
    <li><b>A pop-up do desenho bate no teto de 717&nbsp;px e rola por dentro</b> (mostra 478 de 658, esconde 180). É o padrão da casa, e o topo com o título e o rodapé com o <b>{MAPA["ROTULO_FECHAR"]}</b> ficam sempre à vista. <b>A janela GTK de verdade NÃO rola</b> — 720×520 num <code>Gtk.Box</code> puro, sem <code>ScrolledWindow</code> em lugar nenhum: com este conteúdo, o que sobra fica fora e ninguém avisa. É defeito a consertar, e o mockup já mostra a cura.</li>
    <li><b>“entrada 1 de 1” conta APARELHO, não entrada</b> — e a palavra é do produto. Um passo de hub coloca vários aparelhos de uma vez, e mesmo assim o contador diz “entrada”. Fica registrado; a redação é da <code>CONFIGURACOES-O-LEXICO-01</code>.</li>
    <li><b>Um aparelho aparece como “Aparelho de entrada”, e não como “DualSense”.</b> O censo classifica pela <i>interface 0</i>, e o próprio produto escreve que o DualSense por cabo é <code>03/00/00</code> — classe de entrada sem protocolo de arranque. Não inventei o rótulo: é o que a tela mostraria. E é ele que acende a terceira linha da confissão.</li>
    <li><b>A ordem da confissão é minha, e no produto ela é SORTEADA.</b> As lacunas vivem num <code>set</code>, e um <code>set</code> de textos não tem ordem estável entre execuções: as mesmas três linhas saem em ordens diferentes a cada abertura. A tela as mostra na ordem em que o produto as declara. <b>É defeito, e é de uma linha.</b></li>
  </ul>

  <h2>MODO não é MÁSCARA, e nada nesta tela diz que você perde o microfone</h2>
  <ul>
    <li><b>O microfone segue o TRANSPORTE, e a máscara não o toca.</b> Pelo cabo o DualSense expõe uma placa USB Audio própria e o PipeWire a publica sozinho (medido em 15/08/2026: duas placas ALSA, ~475.000 amostras não-zero cada). Pelo rádio não existe placa nenhuma — o aparelho não anuncia A2DP, HFP nem HSP —, e o áudio vem em Opus <i>dentro</i> do relatório HID 0x31: quem o traz é a ponte do Hefesto, que publica uma fonte de captura do PipeWire. <b>No rádio o microfone já é emulado hoje</b>, com outro nome.</li>
    <li><b>Por isso a chavinha “pelo cabo / pelo rádio” SAIU.</b> Ela oferecia uma escolha que o transporte já tinha feito — e o próprio mockup se contradizia: o gerador já derivava o caminho do transporte e desenhava a chavinha ao lado. Ponto final dela, 28/08: <i>“se tiver em modo rádio, então o mic é modo rádio”</i>. Os {num(CUSTO_DO_MIC)} turnos viraram <b>consequência</b>, e a tela os mostra na régua de Desempenho em vez de perguntar por eles.</li>
    <li><b>Nenhum aviso de máscara, em máscara nenhuma</b> — e o motivo é mais forte do que “o Pro só não tem microfone”. A máscara limita o que o <b>jogo</b> recebe, não o que o <b>controle</b> faz: o Hefesto continua acendendo a barra de luz, aplicando o gatilho e lendo o giro do DualSense físico em qualquer máscara. E a lacuna mais visível — o mic — tem cura: o estado <b>Emulado</b> da <code>ONDA-CONEXOES-06</code> entrega o áudio por um dispositivo que qualquer jogo enxerga, independentemente da máscara.</li>
    <li><b>Nativo e Emulado desceram de escolha para LEITURA.</b> Com o transporte explícito e a máscara explícita por controle (aba Jogar), o resultado fica determinado: cabo → a placa do próprio aparelho; rádio → a ponte. Sobraram <b>dois estados</b> — Ligado e Desligado —, e a tela <b>diz</b> o caminho em vez de perguntá-lo. O “Automático” não entra: a heurística que o moveria (<code>integrations/api_de_entrada.py</code>) errou em <b>13 de 14</b> dos jogos dela.</li>
  </ul>

  <h2>Um número desta tela estava ERRADO pelo dobro, e nenhuma régua o via</h2>
  <ul>
    <li><b>A dica do teto dizia que “Bateria longa” corta a força em 60%. O produto corta em {fala_do_teto(COM_TETO)}.</b> O degrau tem um dono só — <code>RUMBLE_POLICY_MULT["{COM_TETO}"]</code> —, e é dele que o <code>secao_orcamento</code> deriva a frase, com o cuidado escrito no próprio arquivo: <i>“escrever «30%» à mão nesta tela”</i> é o que ele existe para evitar. Aqui o 60 estava digitado. Agora é lido por AST, como os sete números do rádio já eram — <b>oito literais a menos</b>.</li>
    <li><b>A máscara e a bateria da linha fechada não são digitadas aqui, e nem no mesmo lugar.</b> A bateria vem do <code>ESTADO</code> da aba <b>Controles</b>, lido por AST — não por <code>import</code>, que <i>executaria</i> o gerador da outra aba e reescreveria o HTML dela. A máscara vem da <code>monta.MESA</code>, que virou o dono único dela em 28/08: o P2 aparece como <b>{POR_PREF["p2"]["mascara"]}</b> aqui, na Jogar e na Controles porque é o mesmo dado, não porque três listas concordam — e elas não concordavam.</li>
  </ul>

  <h2>O acordeão, em CSS puro — e o que ele não consegue</h2>
  <ul>
    <li><b>Zero JavaScript.</b> O mockup inteiro não tem uma linha de script, e o cruzamento do mapa do controle já é feito só com <code>:has()</code>. Aqui a peça é um grupo de <code>&lt;input type=radio&gt;</code> escondido: cada linha fechada é um <code>&lt;label&gt;</code> que marca o seu. Por ser rádio, <b>marcar um desmarca os outros</b> — que é, ao pé da letra, “clicar num abre e fecha os outros”.</li>
    <li><b>Clicar numa linha muda a fita, de verdade.</b> As {len(ESTADOS)} regras que repintam os chips são geradas da <code>MESA</code> e casam <b>pela posição</b> do chip, não pelo texto dele — o texto do chip já mudou uma vez e matou a fita viva em silêncio.</li>
    <li><b>“Todos abre os {len(MESA)}” existe, e o gesto está no lugar possível.</b> O chip “Todos” é um <code>&lt;span&gt;</code> do esqueleto (<code>monta.fita()</code>), e um <code>&lt;span&gt;</code> não vira alvo de clique sem tocar o <code>monta.py</code> — que esta aba não toca. Então o gesto mora na própria linha <b>aberta</b>: clicar nela volta para “Todos”, com os {len(MESA)} abertos, e o <code>title</code> diz isso. Para o chip da fita clicar de verdade, o <code>monta.fita()</code> precisa emitir <code>&lt;label&gt;</code> em vez de <code>&lt;span&gt;</code> — é uma linha lá, e vale para as dez abas.</li>
    <li><b>No estado “Todos” a seta de abrir virou a palavra <code>só este</code>.</b> As {len(MESA)} linhas mostravam <b>▾</b> com a dica <i>“Abre este controle”</i> — {len(MESA)} setas de abrir sobre {len(MESA)} linhas já abertas, e a dica mentia duas vezes: a linha estava aberta, e o que o clique faz ali é <b>fechar as outras</b>. A dica do corpo da linha também mudou, e agora é a mesma nos dois estados — <i>“deixa só este controle aberto, os outros fecham”</i> é verdade tanto na linha fechada quanto nas {len(MESA)} abertas. <b>Foi preciso</b>: <code>title</code> não muda com CSS, então uma frase que só vale num estado mente no outro. A coluna da seta ficou com <b>largura fixa</b> pela mesma razão que as colunas do resumo: se ela mudasse de tamanho ao clicar, os {len(MESA)} percentuais de bateria andariam de lado juntos.</li>
  </ul>

  <h2>O que saiu, e o que cada saída pagou</h2>
  <ul>
    <li><b>“Microfone e botões” saiu do quadro e entrou nas linhas dos controles</b> — <b>86&nbsp;px</b> com a margem da sub-seção. Os dois campos que valiam para a máquina inteira agora são de cada controle, que é onde a pergunta tem resposta: o botão do mic é <i>daquele</i> aparelho.</li>
    <li><b>“Botões do controle externo” saiu da tela.</b> Nintendo e 8BitDo estão fora do escopo agora, por decisão dela — vira sprint. Nada substituiu o campo.</li>
    <li><b>“O que só você sabe” saiu, e ele não paga nada</b>: a coluna tinha <b>110&nbsp;px</b> de conteúdo contra <b>150</b> da coluna do exame, que é quem manda na altura do quadro. As duas perguntas foram para o <b>{MAPEAR_ENTRADAS}</b> — e lá elas preenchem um vazio real: hoje a janela do desenho cria face com <code>perto=False, alto=False</code> e <b>não tem um único gesto</b> que mude os dois; ela não guarda nenhum fato que só você tem.</li>
    <li><b>O dropdown de cor saiu das linhas dos controles.</b> Quem o produto lê aparece na borda; quem ele não lê fica com <b>borda neutra, e está dito</b> — no “?” do quadro e no <code>title</code> da linha. Os {len(NO_RADIO)} controles no rádio são os de borda neutra, porque o Hefesto <b>ainda não pergunta a cor pelo rádio</b> (<code>ONDA-CONEXOES-11</code>).</li>
    <li><b>A moldura dos {len(MESA)} cartões saiu, e ela pagava {Q_GESTAO_ANTES - Q_GESTAO}&nbsp;px.</b> Quatro bordas de 2&nbsp;px mais os 27 de vão entre eles somavam mais altura do que uma linha inteira de controle — e não mostravam nada. <b>A cor lida não se perdeu:</b> ela virou a barra de 3&nbsp;px na aresta esquerda de cada linha, que é a mesma promessa e agora cai numa coluna só, alinhada nas {len(MESA)} — mais fácil de comparar do que {len(MESA)} retângulos soltos.</li>
    <li><b>As lâmpadas de jogador saíram dos desenhos pequenos.</b> Neste tamanho elas medem 1,0 × 0,33&nbsp;px — tinta que ninguém vê. A barra de luz ficou, e ela é a cor do <i>jogador</i>.</li>
  </ul>

  <h2>O teto da vibração está nos dois, e a tela diz qual vale</h2>
  <ul>
    <li><b>O global é o da mesa, e ele MUDOU DE ABA.</b> O dropdown dos três perfis saiu daqui e foi para a <b>{ABA_DO_TETO_GLOBAL}</b>, onde se chama <b>{CASA_DO_TETO_GLOBAL}</b> — palavra dela, 28/08: <i>“Teto da Vibração, que na verdade é Perfil de Bateria”</i>. O código já lhe dava razão antes do nome: <code>secao_orcamento.py:127</code> chama a chave de <code>PERFIL_BATERIA_LONGA</code>, e a <code>D-PERFIL-DE-DESEMPENHO</code> (24/08) diz que <i>“o perfil decide o que custa BATERIA”</i>. Esta aba continua <b>lendo</b> o global — hoje <b>{ORC["ROTULOS_DOS_PERFIS"][PERFIL_DA_MESA]}</b>, que é <b>{TETO_GLOBAL}</b> —, e o que fica dela é a régua de turnos, que mede o <b>rádio</b>, não a bateria.</li>
    <li><b>O do controle sobrepõe</b>, e o campo de cada linha mostra qual é o caso: o P{POR_PREF["p3"]["jogador"]} está com a bateria em {DA_CONTROLES["p3"]["bat"]}% e sobrepõe com <b>{fala_do_teto(COM_TETO)}</b>; os outros dizem <b>{SEGUE_O_GLOBAL}</b>. A conta feita — <b>qual dos dois está valendo, de onde ele veio, e em que aba o global se muda</b> — está no <code>?</code> ao lado do campo, e não mais numa coluna de texto ao lado dele.</li>
    <li><b>Isso nasce como sprint sobre o que já existe.</b> A <code>POR-UNIDADE-01</code> (10/08) já grava política de vibração POR CONTROLE (<code>profiles/manager._controllers_to_rumble_scales</code>), relativa à global. <b>Falta uma frase sua:</b> quando o controle sobrepõe, ele vence sempre, ou o produto aplica o <code>min</code> como faz hoje entre o orçamento e a política? O <code>min</code> é o que impede um “teto” de <i>aumentar</i> a força.</li>
  </ul>

  <h2>O terceiro quadro voltou para a tela — e o que ainda não cabe</h2>
  <ul>
    <li><b>“Rádio e adaptadores” mostrava {VISIVEL_3_ANTES}&nbsp;px de {Q_RADIO}: a barra do título, e mais nada.</b> Hoje mostra <b>{VISIVEL_3}</b> — título e a primeira linha do corpo, que é o piso que a régua passou a exigir. E isso <b>não</b> se conseguiu encolhendo o terceiro quadro: só quem está <b>acima</b> de um quadro decide quanto dele aparece. Os dois da frente somavam {Q_EXAME + Q_GESTAO_ANTES}&nbsp;px e o teto é <b>{TETO_DOS_DOIS}</b>; agora somam {Q_GESTAO + Q_EXAME}.</li>
    <li><b>Os {Q_GESTAO_ANTES - Q_GESTAO}&nbsp;px vieram de dois lugares, e nenhum deles é conteúdo.</b> A <b>Gestão de Controles</b> virou uma <b>lista emoldurada</b> em vez de {len(MESA)} cartões soltos: {len(MESA)}×4&nbsp;px de borda mais 27 de vão somavam <b>43&nbsp;px que não mostram nada</b> — mais do que uma linha inteira de controle —, e a lista os troca por 5&nbsp;px de fio: <b>saldo de 38</b>. Os outros <b>8</b> saíram do respiro do corpo aberto, que era 48 e é 40 — o campo continua com os {H_ESCOLHA} do token <code>--h-escolha</code>, o que saiu foi padding, e no estado “Todos” esses 8 valem por {len(MESA)}. <b>A ordem dos quadros não pagou px nenhum</b>: ela mudou de <i>onde</i> os px caem, que é o que decide o que aparece.</li>
    <li><b>E a nova ordem também lê melhor.</b> Os controles vêm primeiro — é o que a pessoa veio ver —, e o exame da sala desceu para junto do inventário dela: o exame fala da <b>“Entrada 3”</b>, e a tabela que diz o que está na Entrada 3 agora é a de baixo, e não a de outro lugar da aba.</li>
    <li><b>A aba mede {ALTURA}&nbsp;px e o miolo mostra {VISIVEL}: ficam {ESCONDE}&nbsp;px por dentro</b> (eram {ESCONDE_ANTES}). No estado <b>“Todos”</b>, {ESCONDE_TODOS} (eram {ESCONDE_TODOS_ANTES}) — e ali a <b>Gestão de Controles inteira cabe</b>, com os {len(MESA)} abertos: antes o P{MESA[-1]["jogador"]} ficava cortado no meio.</li>
    <li><b>O que AINDA não cabe, e o número é este: no estado “Todos” o terceiro quadro continua em ZERO.</b> A conta é fria — com os {len(MESA)} abertos a Gestão de Controles mede {TODOS}&nbsp;px (eram {TODOS_ANTES}), e {TODOS} + {Q_EXAME} = {TODOS + Q_EXAME} contra o teto de {TETO_DOS_DOIS}. <b>Faltam {TODOS + Q_EXAME - TETO_DOS_DOIS}&nbsp;px</b>, e não há onde tirá-los sem cortar: cada corpo aberto é uma linha de campo de {H_ESCOLHA}&nbsp;px, que é o token <code>--h-escolha</code> desta casa.</li>
    <li><b>Se a aba tiver de caber INTEIRA, o que teria de sair — e o preço de cada um.</b> A seção <b>“Desempenho”</b> ({DESEMPENHO}&nbsp;px), a <b>tabela dos adaptadores com os dois botões</b> ({INVENTARIO}), ou o quadro <b>“Está tudo certo?”</b> inteiro ({Q_EXAME}). <b>A decisão é sua</b> — nenhuma delas foi tomada aqui. Note o que <b>não</b> paga nada: as cinco linhas do exame não encolhem sem sumir uma, e a fileira dos rádios vizinhos não manda na altura da coluna em que está — tirá-la economiza zero.</li>
    <li><b>Mas na SUA janela ela já cabe.</b> Numa tela de {num(ALT_TV)}&nbsp;px o miolo tem {UTIL_TV}&nbsp;px de conteúdo, e a aba agora pede {ALTURA - 34}: <b>sobram {UTIL_TV - (ALTURA - 34)}&nbsp;px</b>. Antes desta leva faltavam 9. A janela abre com 757 nas dez abas porque foi assim que a Jogar foi aprovada — se a altura da janela subir, esta aba deixa de esconder qualquer coisa, e é <b>uma</b> decisão para as dez, não dez.</li>
  </ul>

  <h2>Escolhas que precisam do seu aval</h2>
  <ul>
    <li><b>A ordem dos quadros mudou, e é a mudança que devolveu o terceiro para a tela.</b> “Gestão de Controles” passou a vir <b>primeiro</b>, e “Está tudo certo?” desceu para junto de “Rádio e adaptadores”. Duas razões: a aritmética (só quem está acima decide quanto do de baixo aparece, e não havia arranjo com o exame na frente em que o terceiro coubesse), e a leitura — o exame fala da <b>Entrada 3</b>, e a tabela que diz o que está na Entrada 3 agora é a de baixo, não a de outro lugar. <b>Se você preferir o exame na frente</b>, ele volta: o preço é o terceiro quadro voltar a mostrar {VISIVEL_3_ANTES}&nbsp;px.</li>
    <li><b>“Vale Sem teto, do global, abaixo” SAIU — e o desempate que esta linha pedia deixou de existir.</b> Ela mandou tirar a leitura e deixar só o seletor (<code>D-O-SEM-TETO-SAI-DOS-DOIS-LUGARES</code>), e a frase saiu dos <b>dois</b> lugares em que estava: destas {len(MESA)} linhas de controle (o que ela via) e da capa do Desempenho (y=834, fora da dobra — o que casava letra por letra com o pedido, e que ela não podia ter visto). O <b>“abaixo”</b> caducou de qualquer jeito, por uma segunda razão independente: com o teto global mudando-se para a <b>{ABA_DO_TETO_GLOBAL}</b>, o endereço que a frase dava aponta para um lugar que não existe mais nesta aba. <b>A frase não se perdeu</b> — ela vive no <code>?</code> do campo, que a lê sob demanda em vez de gastar uma coluna nas {len(MESA)} linhas. E o desempate que este item pedia (“o teto global morar na mesma moldura dos {len(MESA)} tetos de controle”, por {H_ESCOLHA + 9}&nbsp;px) está <b>respondido</b>: o global saiu da aba inteira, e não custa px nenhum aqui.</li>
    <li><b>Os quatro botões viraram UMA fileira, e ela custou zero.</b> Você escreveu a ordem com todas as letras — <i>“Examinar de novo. / Já Movi - Reexaminar. / Ignorar / Ver Ordens ignoradas.”</i> — e com um par em cada coluna essa ordem não existe: a leitura de uma grade de duas colunas é esquerda→direita, e “Ignorar” (que estava à direita) teria de vir antes de “{VER_IGNORADAS}” (que estava à esquerda). <b>Medido:</b> o quadro tinha 204&nbsp;px e continua com {Q_EXAME}; a fileira nasce no mesmo y=575; os quatro botões passaram de 265,5 para <b>272&nbsp;px cada</b>, todos iguais, e a borda direita não andou um pixel.</li>
    <li><b>“Ver as ordens caladas” virou “{VER_IGNORADAS}”, e o motivo é o PAR.</b> O botão irmão chama-se <b>Ignorar</b>: quem o aperta procura depois as ordens <i>ignoradas</i>. “Caladas” era a única palavra da dupla sem par na tela. <b>Uma diferença para a sua frase:</b> você escreveu “Ver Ordens ignoradas” e a tela diz “Ver <u>as</u> ordens ignoradas” — o artigo é o que já estava lá, e só a última palavra mudou. Se você quiser a sua frase ao pé da letra, é <b>uma</b> palavra a menos.</li>
    <li><b>A seção continua chamando-se “Desempenho”, e a escolha é minha — derrube-a numa frase.</b> Ela perdeu o dropdown para a <b>{ABA_DO_TETO_GLOBAL}</b> e sobrou só a régua. Foi proposto renomeá-la para <b>“Rádio em uso”</b>, e a proposta cai numa medição de duas palavras: o subtítulo é frase <i>sua</i> (“o rádio de cada adaptador, em fatias”), então o rótulo ficaria <b>“Rádio em uso • O rádio de cada adaptador, em turnos”</b> — “rádio” duas vezes em oito palavras. Trocar o subtítulo para desfazer a repetição seria mexer na sua frase. E “Desempenho” não fica órfão: com o perfil noutra aba e com outro nome, sobra <b>um sentido só</b> para a palavra nesta tela — quanto do tempo do rádio está em uso.</li>
    <li><b>O gesto de voltar para “Todos” está na própria linha aberta</b>, e não no chip da fita. O chip vira clicável com uma linha no <code>monta.fita()</code> — e aí ele passa a valer para as dez abas de uma vez.</li>
    <li><b>“Adaptadores Bluetooth” continua sendo título novo na tela.</b> Ele existe para a coluna da esquerda ser irmã da direita. É palavra nova, e a palavra é sua.</li>
    <li><b>O resumo da linha fechada virou grade</b>: máscara, microfone e bateria repartem a linha em <code>126fr 272fr 76fr</code> — as três larguras <i>naturais</i> medidas, e não três números escolhidos. Assim as colunas caem no mesmo x nas {len(MESA)} linhas sozinhas, os percentuais terminam juntos, e o vão de 350&nbsp;px que sobrava entre o nome e um resumo encostado à direita desapareceu. É o mesmo remédio das quatro barras de bateria da aba Controles.</li>
    <li><b>Dois controles do mesmo plástico continuam com a borda idêntica</b> — e agora também com dois blocos idênticos na régua do rádio. O número do jogador dentro do bloco atenua, mas não resolve.</li>
    <li><b>Onde as declarações desta aba gravam?</b> Continua aberto, e agora com um caso concreto: o microfone é da <b>máquina</b> ou do <b>perfil</b>? A sua resposta de 28/08 foi <i>“nos dois: a máquina decide o padrão, o perfil sobrepõe”</i> — a tela ainda não mostra o recibo disso.</li>
    <li><b>Qual régua manda no arranjo</b> (<code>D-QUAL-REGUA-MANDA-NO-ARRANJO</code>) — a tela mostra a receita, que é o que o código tem; se o juízo por entrada vencer, o texto do imperativo muda.</li>
  </ul>
</div>

</body>
</html>
'''

n = monta("08-conexoes", "Conexões", MIOLO, CSS, fita_viva=True, legenda=LEGENDA)

# ---------------------------------------------------------------------------
# AS QUATRO TELAS ENTRAM IRMÃS DA `.janela`, fora do miolo.
#
# `monta()` não tem parâmetro para pop-up, e não devia ter: a `.tela-nova` é
# `position:fixed`, logo ela não pertence ao miolo nem custa um pixel dele.
# É a mesma injeção que o `aba06.py` faz desde 28/08, na mesma marca.
# ---------------------------------------------------------------------------
p = onde.pagina("08-conexoes.html")
x = p.read_text()
MARCA = "<!-- ================= LEGENDA DO MOCKUP ================= -->"
if MARCA not in x:
    raise SystemExit("ERRO: a marca da legenda mudou no fim.html")
TELAS = "\n".join(t.strip() for t in (TELA_MAPEAR, TELA_SENTADA, TELA_FIM, TELA_EM_PE))
x = x.replace(MARCA, TELAS + "\n\n" + MARCA, 1)

# ---------------------------------------------------------------------------
# O ENDEREÇO DOS CHIPS DA FITA — `IDENTIDADE-VEM-DE-CIMA-01`, 03/09/2026.
#
# O PRODUTO JÁ ESCREVE A FITA INTEIRA, e há mais de um dia:
# `hefesto_vivo.py` monta `carga["fita"] = _fita(ctx.mesa)` a cada tique e o
# `pintar()` faz `f.outerHTML = p.fita` — com a mesa VIVA, pelo mesmo
# `monta.fita()` que desenhou o mockup. O que faltava era a página DIZER isso:
# sem `data-campo`, os dois chips do desenho ("P1 · Cosmic Red · USB",
# "P2 · Starlight Blue · BT") contam como identidade congelada em toda régua
# desta casa — seis dos quinze achados desta aba eram só isto.
#
# COM O ENDEREÇO, A `regua_do_mockup` os julga PRODUTO pelo caminho que ela já
# tem: o chip endereçado SOME do DOM quando a fita se troca inteira, e um campo
# que sumiu é *"o bloco que continha este campo foi TROCADO pelo produto — o
# desenho não sobreviveu, que é o que se queria"* (`regua_do_mockup:_classificar`).
#
# **O REMENDO MORREU — 03/09/2026, e a promoção já tinha acontecido.** Este
# bloco escrevia o `data-campo` aqui porque `monta.py` é das DEZ abas e dez
# agentes editando a mesma linha seria conflito garantido; ficou escrito que *"o
# lugar definitivo é `monta.fita()`, e quem integrar as dez pode promovê-lo lá e
# apagar este bloco"*. Promovido ele foi (`monta.py:536`) — e o `apagar` não.
#
# O PREÇO ERA SILENCIOSO E SÓ APARECIA A QUEM RODASSE O GERADOR: com o atributo
# nos dois lugares, cada chip saía com `data-campo="fita-chip"` DUPLICADO. O
# navegador fica com o primeiro e a tela não muda uma letra — mas a página
# publicada e a que o gerador produz deixaram de ser a mesma, que é a divergência
# que a `mockup/` existe para não deixar acontecer.
#
# A CONTAGEM FICA, e é ela que morde: um chip a mais ou a menos que a mesa
# continua derrubando o gerador.
_CHIP = '<span class="chip plastico'
_quantos = x.count(_CHIP)
if _quantos != len(CONECTADOS):
    raise SystemExit(
        f"ERRO em 08-conexoes: a fita tem {_quantos} chips de plástico e a mesa "
        f"tem {len(CONECTADOS)} conectados. O endereço da identidade não pode "
        f"cair em cima de um chip que não existe — nem faltar num que existe.")

onde.gravar("08-conexoes.html", x)


# ---------------------------------------------------------------------------
# AS QUATRO RÉGUAS DA CONEXÕES — 31/08/2026, e cada uma guarda um pedido dela.
# Elas leem o HTML JÁ GRAVADO, que é a última coisa que a página é.
# ---------------------------------------------------------------------------
_HTML = onde.pagina("08-conexoes.html").read_text()
_falhas = []


def _exigir(cond, queixa):
    if not cond:
        _falhas.append(queixa)


# 1. ABRIR UMA MINIMIZA AS OUTRAS. Três rádios com o MESMO `name` — com
#    `checkbox` as três abriam juntas e a página passava 248px do miolo.
_ABRE = re.findall(r'<input class="abre" type="(\w+)"(?: name="([^"]*)")?', _HTML)
_exigir(len(_ABRE) == 3, f"não são 3 seções que expandem, e sim {len(_ABRE)}")
_exigir(all(t == "radio" for t, _ in _ABRE),
        "uma seção voltou a ser `checkbox` — duas abertas ao mesmo tempo é o que "
        "ela mandou desfazer: *abrir uma expansão minimiza a outra*")
_exigir(len({n for _, n in _ABRE}) == 1 and _ABRE[0][1],
        "os rádios das seções não dividem o mesmo `name` — sem isso o navegador "
        "não tem como fechar a outra")

# 2. O RESPIRO DO RÓTULO QUE EXPANDE. O `.quadro-topo` do esqueleto é
#    `padding:11px 14px 0`: sem esta regra sobra 1px embaixo do texto.
_exigir(".quadro:has(> input.abre) .quadro-topo{padding-bottom:11px}" in _HTML,
        "o rótulo das seções que expandem perdeu o respiro de baixo — volta a "
        "1px contra os 12 de cima, que é o que ela viu nas duas fotos")

# 3. O LUGAR DE QUEM NÃO ESTÁ NA MESA. As duas metades: o nome novo presente, e
#    o rótulo de mesa daquele controle AUSENTE — tirar só uma delas foi como uma
#    cura desta casa passou pela metade em 31/08.
_FORA = [c for c in MESA if not c.get("conectado", True)]
_exigir(_HTML.count("Desconectado</span>") == len(_FORA),
        f"não são {len(_FORA)} lugares 'Desconectado' na Gestão de Controles")
for _c in _FORA:
    _exigir(rotulo(_c) not in _HTML,
            f"o rótulo de mesa do Player {_c['jogador']} continua na tela — ele não está na mesa")

# 4. QUEM CONTA CONTROLE CONTA QUEM ESTÁ NA MESA. A aba contava quatro em
#    silêncio: o Check-up prometia energia para "os 2 controles no cabo" contando
#    o P4, que não está.
#    A RÉGUA REFAZ A CONTA A PARTIR DA `MESA`, e NÃO lê `NO_CABO`/`CONECTADOS`.
#    Escrita como `f"{len(NO_CABO)} controle" in _HTML` ela PASSOU na mordida que
#    devolvia `NO_CABO = [... for c in MESA ...]`: o HTML nascia do mesmo valor
#    errado que a régua usava para procurar, e os dois concordavam. Uma régua que
#    compara o produto com a variável que o produziu não mede nada — mede a si
#    mesma. Aqui os números saem do HTML e a verdade sai de `MESA` + `conectado`.
_na_mesa = [c for c in MESA if c.get("conectado", True)]
_cabo = len([c for c in _na_mesa if c["via"] == "USB"])
_radio = len([c for c in _na_mesa if c["via"] == "BT"])


def _numero(padrao, onde_diz):
    achado = re.search(padrao, _HTML)
    if not achado:
        _falhas.append(f"a régua não achou {onde_diz} no HTML — seletor cego é ERRO, "
                       "não silêncio")
        return None
    return int(achado.group(1))


_exigir(_numero(r">(\d+) na mesa", "a contagem do cabeçalho") == len(_na_mesa),
        f"o cabeçalho da Gestão não conta os {len(_na_mesa)} que estão na mesa")
_exigir(_numero(r"energia para o?s? ?(\d+) ", "a frase da energia") == _cabo,
        f"o Check-up não fala dos {_cabo} controle(s) no cabo — ele voltou a contar "
        "quem não está na mesa")
_exigir(_numero(r"<b>Por que importa:</b> (\d+) ", "a frase do rádio") == _radio,
        f"a frase do rádio não fala dos {_radio} controle(s) no rádio")
_exigir(_numero(r"dos seus (\d+) controles", "o total da frase do rádio") == len(_na_mesa),
        f"a frase do rádio não fala dos seus {len(_na_mesa)} controles")

if _falhas:
    raise SystemExit("ERRO em 08-conexoes — decisão dela desfeita:\n  "
                     + "\n  ".join(f"- {f}" for f in _falhas))

print(f"08-conexoes: OK, {n} divs · 4 telas novas "
      f"(1 do desenho + {3} da cerimônia) · 3 seções exclusivas · "
      f"{len(CONECTADOS)} na mesa + {len(_FORA)} desconectado(s)")
