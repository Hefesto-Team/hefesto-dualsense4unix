import ast
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from monta import (  # noqa: E402
    MESA,
    CONECTADOS,
    botao_cinza,
    monta,
    CSS_GLIFO,
)

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
import onde  # noqa: E402
from onde import RAIZ as R  # noqa: E402

# O PISO DO MIOLO TEM UM DONO SÓ, e ele mora na ponte da janela — §3.5 da
# ALTURA-DA-VISTA-01. Custa 0,13 s e NÃO abre tela: o módulo importa o `gi`
# dentro da função que cria a janela, não no topo.
from hefesto_dualsense4unix.gui import ponte_da_tela as _ponte  # noqa: E402

# ---------------------------------------------------------------------------
# A MESA MANDA NOS NÚMEROS DESTA ABA.
#
# Nada aqui digita "quatro". A aba Sistema é, do começo ao fim, uma CONTAGEM —
# quantos aparelhos existem, quantos o Hefesto criou, quantos o jogo enxerga —
# e uma contagem digitada é a que diverge no dia em que a mesa muda. Foi assim
# que o cabeçalho dizia "2 controles" com quatro chips na fita, em 27/08.
# ---------------------------------------------------------------------------
# O `N` CONTA OS CONECTADOS — 01/09/2026, e era o mesmo defeito de três outras
# abas hoje: a tela dizia *"Os 4 controles"* com dois na mesa. A `MESA` sabe dos
# quatro LUGARES; toda frase que promete alcance tem de contar os ocupados.
N = len(CONECTADOS)
LUGARES = len(MESA)
USB = [c for c in CONECTADOS if c["via"] == "USB"]
BT = [c for c in CONECTADOS if c["via"] == "BT"]
#: A CONTA DOS NÓS DE `/dev/input/js*` SAIU DA TELA — 11/09/2026, A1-032. Ela
#: era `2 * N + N` (cada DualSense publica DOIS — o gamepad e os sensores de
#: movimento —, e cada gamepad virtual publica um) e aparecia na nota do co-op.
#: Caminho de kernel na tela é da mesma família de `uinput` e `hidraw`, que o
#: glossário proíbe, e a frase acima já explicava o co-op inteiro. A conta
#: continua viva onde ela tem dono: `emulation_actions._chave_do_aparelho`.


#: MEDIDO no Chrome (1920×1080) com o `olhar.py` desta pasta, 28/08/2026 — e é
#: número de FOTO: mexeu no miolo, meça de novo antes de repetir a frase.
#: O miolo desta janela tem `MIOLO_H` de altura útil; o conteúdo da aba mede
#: `ALTURA`. Enquanto `ALTURA <= MIOLO_H`, nada rola por dentro e nada é fatiado.
#: REMEDIDOS EM 06/09/2026, e os dois estavam ERRADOS — não caducos, errados.
#: O par dizia `544, 542`; medido de novo no Chrome, pelo mesmo caminho de
#: sempre, o miolo tem **564** e o conteúdo tinha **508**. A folga real era de
#: 22px, e não de 2 — e o `.quadro` não a preenche, porque o miolo ainda gasta
#: 34px de recuo (16 em cima, 18 embaixo) que o número velho contava dentro.
#:
#: O NÚMERO ERRADO CUSTA, e custou aqui: com ele, o quarto botão dos gestos
#: raros parecia impossível antes de alguém abrir o navegador. A conta de hoje,
#: medida: `.avancado` foi de 110 para 136 (o botão novo, sem vão entre eles) e
#: o vão entre faixas caiu 2px em cada `sec-alta` — a página fecha em **530 de
#: conteúdo para 530 de espaço útil**, e o miolo não rola um pixel.
#:
#: O `MIOLO_H` DEIXOU DE SER DIGITADO — 10/09/2026, §3.5 da ALTURA-DA-VISTA-01.
#: Ele dizia **564**, que era o miolo de uma janela de altura FIXA; no instante
#: em que a altura passou a seguir a vista (decisão dela, «1 + rodapé») esse
#: número parou de ser verdade em qualquer tela.
#:
#: A REGRA QUE O RESOLVE: *um gerador não pode assegurar contra a vista, porque
#: ele roda sem tela.* Ele assegura contra o PISO — a menor vista prometida —,
#: e quem mede a vista de verdade é
#: `scripts/ensaios/a_janela_cabe_no_que_ela_ve.py --vista=N`, com a janela
#: aberta. O dono do piso é um só: `gui/ponte_da_tela.MIOLO_NO_PISO`.
#:
#: NA TELA DELA ELE SOBRA, e é o ponto do piso: medido com a vista de 840 px
#: da TV dela, o miolo desta aba vai a **666**, não a estes 634. Assegurar
#: contra o menor é o que faz a promessa valer nas duas pontas.
MIOLO_H, ALTURA = _ponte.MIOLO_NO_PISO, 530


def _lista(nomes):
    """`a`, `b` e `c` — em português, com "e" antes do último."""
    return nomes[0] if len(nomes) == 1 else f"{', '.join(nomes[:-1])} e {nomes[-1]}"




def _frase(nomes, curto=True):
    """A mesma lista, em CAIXA DE FRASE: só a primeira letra é maiúscula.

    Regra dela, 30/08: *"a maiúscula a regra é sobre a primeira letra a ser
    capitalizada"*. `LINHAS_DO_TETO` guarda cada nome capitalizado porque lá
    cada um é um TÍTULO de linha; enroladas num valor de campo só, elas viram
    uma frase — e "Gatilhos, Barra de luz e Giroscópio" tem três maiúsculas no
    meio de uma. Nenhum dos nomes é próprio, caminho ou sigla, então nenhum
    perde forma ao descer. Derivado, nunca digitado: o dono continua sendo o
    produto.
    """
    # `curto=False` devolve a frase INTEIRA, e é o que vai para o `title`.
    # Encurtar sem guardar o completo em lugar nenhum não é simplificar — é
    # apagar: "barra de luz" e "microfone POR RÁDIO" carregam o qualificador que
    # diz de qual microfone se fala.
    curtos = [APELIDO_NA_TELA.get(n, n) for n in nomes] if curto else list(nomes)
    return _lista([curtos[0]] + [n[0].lower() + n[1:] for n in curtos[1:]])


# ---------------------------------------------------------------------------
# O PERFIL DE BATERIA SAI DO PRODUTO, LIDO POR AST — NENHUM RÓTULO DIGITADO.
#
# Os três rótulos, a tradução perfil->disco e o degrau do teto têm dono no
# produto (`app/actions/config/secao_orcamento.py` e `daemon/subsystems/
# rumble.py`). Digitá-los aqui é o defeito que aquele módulo existe para
# evitar, e ele já mordeu esta casa: em 28/08 a dica da Conexões afirmava que
# "Bateria longa" corta a força em 60%, e o produto corta em 30% —
# `RUMBLE_POLICY_MULT["economia"] = 0.3`. O dobro do limite real, e nenhuma
# régua podia vê-lo, porque era literal.
#
# POR AST E NÃO POR IMPORT, pela mesma razão do `aba08.py`: importar o módulo
# do produto puxa `structlog` e a GUI, e o `python3 abaNN.py` desta pasta não
# roda no `.venv`. É o que `scripts/validar-fala-de-tela.py` já faz — "nunca
# importando este módulo".
#
# POR QUE UMA CÓPIA DO LEITOR DO `aba08.py`, e não um import: importar outro
# gerador o EXECUTA, e ele reescreveria o HTML da aba dele (aviso escrito no
# próprio `aba08.py`). O lugar natural deste leitor é o `monta.py`, que é
# território de outro agente nesta rodada; quando ele voltar a ser mexível, as
# duas cópias viram uma.
# ---------------------------------------------------------------------------
def _valor(no, ja):
    """O valor de um nó de AST, resolvendo NOME contra o que já foi lido.

    `ast.literal_eval` sozinho não dá conta de `{PERFIL_TUDO_LIGADO: "Tudo
    ligado"}` — a chave é um `Name`, não um literal. Como o módulo é lido de
    cima para baixo, o nome já está no `ja` quando a linha que o usa aparece.

    `Call` vira dicionário posicional: `LINHAS_DO_TETO` é uma tupla de
    `LinhaDoTeto(nome, vem_de, ponto_de_aplicacao=None)`, e o que esta tela
    precisa dela é só o nome e se existe ponto — o `tem_ponto` do produto.
    """
    if isinstance(no, ast.Name):
        return ja[no.id]
    if isinstance(no, ast.Dict):
        return {_valor(k, ja): _valor(v, ja) for k, v in zip(no.keys, no.values)}
    if isinstance(no, (ast.Tuple, ast.List)):
        return tuple(_valor(e, ja) for e in no.elts)
    if isinstance(no, ast.Call):
        args = [_valor(a, ja) for a in no.args]
        return {"nome": args[0], "tem_ponto": len(args) > 2 and bool(args[2])}
    return ast.literal_eval(no)


def _constantes(caminho, nomes):
    """As constantes de módulo daquele arquivo, lidas sem importar nada.

    Reprova em voz alta quando um nome some: uma constante renomeada no produto
    tem de derrubar a geração da tela, não sumir dela em silêncio.
    """
    ja, achado = {}, {}
    for no in ast.parse(pathlib.Path(caminho).read_text()).body:
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
        except (ValueError, TypeError, KeyError, IndexError, SyntaxError):
            continue  # o que não é literal não interessa — e não pode parar a leitura
        if alvo.id in nomes:
            achado[alvo.id] = ja[alvo.id]
    if faltam := set(nomes) - set(achado):
        raise SystemExit(f"ERRO: {caminho} não tem mais {sorted(faltam)} — "
                         f"a tela dependia deles.")
    return achado


ORC = _constantes(R / "src/hefesto_dualsense4unix/app/actions/config/secao_orcamento.py",
                  {"PERFIS", "ROTULOS_DOS_PERFIS", "TETO_POR_PERFIL", "LINHAS_DO_TETO"})

#: OS ENDEREÇOS E OS GESTOS SÃO DO PRODUTO, NÃO DESTA TELA. Eles moram em
#: `src/hefesto_dualsense4unix/gui/aba_sistema.py` — que é versionado, viaja em
#: worktree e é medido por `ruff`/`mypy` —, e o gerador os LÊ pelo mesmo leitor
#: de AST que já lê o `secao_orcamento`. Digitar a lista aqui criaria o segundo
#: dono: a página passaria a ter endereços que a ponte não conhece, ou o
#: contrário, e nenhum dos dois lados reprovaria.
_CONTRATO = _constantes(R / "src/hefesto_dualsense4unix/gui/aba_sistema.py",
                        {"ENDERECOS", "GESTOS"})
ENDERECOS = _CONTRATO["ENDERECOS"]
GESTOS = _CONTRATO["GESTOS"]

#: OS NOMES LONGOS, ENCURTADOS SÓ PARA A TELA — 01/09/2026, pedido dela.
#:
#: **O DONO MUDOU DE CASA EM 06/09/2026** e é `pacotes/a09_sistema.py`, lido
#: aqui sem importar nada. A razão é que as duas linhas do Perfil de Bateria
#: passaram a ser VIVAS: quem escreve o valor a cada tique é o pacote, e quem
#: escreve o desenho é este arquivo. Digitado nos dois, o apelido se afastaria
#: no dia em que um mudasse — que é como a fita viva morreu calada em 27/08.
#:
#: MEDIDO: a frase inteira tem 303px e a linha dela ocupa TUDO, do rótulo à
#: borda direita do bloco, enquanto as outras três do mesmo quadro ("Nada é
#: limitado", "Os 2 controles", "Vibração") sobram espaço. Ela lê como se
#: estivesse vazando, e é o que ela viu.
#:
#: O DADO NÃO MUDA: o dono da LISTA continua sendo `ORC["LINHAS_DO_TETO"]`, do
#: produto, e a frase INTEIRA continua no `title` do valor — a cura de 31/08 que
#: pôs as reticências também pôs o `title`, e é ele que segura a informação. O
#: que encurta é a etiqueta, e só onde ela não cabe.
#: O ENDEREÇO DO BOTÃO DO MODO IMPROVISADO É LIDO DO PACOTE, nunca digitado —
#: 06/09/2026. O par gerador/pacote já mordeu esta casa uma vez: os dois
#: endereços da fita foram escritos duas vezes, se afastaram, e a fita viva
#: morreu em silêncio em 27/08. Aqui a segunda cópia nem chega a nascer: quem
#: escreve NO campo é `pacotes/a09_sistema.py`, e é de lá que o nome vem.
_DO_PACOTE = _constantes(
    R / "src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py",
    {"APELIDO_NA_TELA", "CAMPO_DO_MODO_AVULSO", "CAMPO_DO_STATUS", "CAMPO_DO_VERDE"})
APELIDO_NA_TELA = _DO_PACOTE["APELIDO_NA_TELA"]
CAMPO_DO_MODO_AVULSO = _DO_PACOTE["CAMPO_DO_MODO_AVULSO"]
#: O Status inteiro e o verde do botão do serviço — os dois endereços que o
#: pacote escreve, lidos dele (25/09/2026), pela mesma razão do de cima.
CAMPO_DO_STATUS = _DO_PACOTE["CAMPO_DO_STATUS"]
CAMPO_DO_VERDE = _DO_PACOTE["CAMPO_DO_VERDE"]


def _id(nome):
    """O endereço de um valor — e ele TEM de estar no contrato do produto."""
    if nome not in ENDERECOS:
        raise SystemExit(f"ERRO: '{nome}' não está em aba_sistema.ENDERECOS. "
                         "A tela não pode ter endereço que a ponte não conhece.")
    return nome


def _gesto(nome):
    """O nome de um gesto — e ele TEM de ter dono declarado no produto."""
    if nome not in GESTOS:
        raise SystemExit(f"ERRO: '{nome}' não está em aba_sistema.GESTOS. "
                         "Um gesto sem dono declarado é um botão que mente.")
    return nome


#: O SUFIXO DA RAZÃO DE UM BOTÃO CINZA — decisão [02] do PO, 04/09/2026.
#:
#: O endereço da razão DERIVA DO GESTO, e não de um nome novo: quem fica cinza
#: é o botão, e o botão É o gesto. `_gesto()` já cobra que ele tenha dono
#: declarado no produto, então nenhuma razão pode nascer apontando para um
#: clique que ninguém atende.
#:
#: POR QUE NÃO UMA ENTRADA EM `aba_sistema.ENDERECOS`: aquele dicionário é o
#: contrato dos VALORES que a camada do produto produz — cada linha dele nomeia
#: a fonte do dado (`state_full["paused"]`, `storm_report:755`). A razão do
#: cinza não é um valor novo do produto: é a MESMA `aba_sistema.travas()` que a
#: aba já consulta desde 03/09, endereçada. É a mesma derivação que o `-g` do
#: glifo faz desde 03/09, e ela vale pelo mesmo motivo — a base tem dono, e o
#: sufixo diz qual metade daquele dono está sendo escrita.
#:
#: `gui/aba_sistema.py` está FORA da posse desta frente, e por isso a derivação
#: fica aqui e é RELATADA. Se um dia `ENDERECOS` ganhar as três linhas, este
#: helper passa a validá-las contra ele sem mudar um `data-campo`.
SUFIXO_DA_RAZAO = "-razao"


def _razao(nome):
    """O `data-campo` onde a razão do cinza daquele gesto é escrita."""
    return f"{_gesto(nome)}{SUFIXO_DA_RAZAO}"


#: AS DUAS LINHAS DO TETO («Com limite», «Sem limite») SAÍRAM EM 25/09/2026,
#: pedido dela: as tabelas de baixo do Perfil de Bateria somem. O dono delas
#: continua sendo `pacotes/a09_sistema.frases_do_teto`, e a frase inteira segue
#: no `?` da coluna.
MULT = _constantes(R / "src/hefesto_dualsense4unix/daemon/subsystems/rumble.py",
                   {"RUMBLE_POLICY_MULT"})["RUMBLE_POLICY_MULT"]
#: A ÚNICA chave de disco que impõe teto. `balanceado`, `max`, `auto` e o
#: não-declarado devolvem `None` em `core.rumble.teto_do_orcamento` — quatro
#: nomes para um comportamento só, e é isso que a `D-PERFIL-DE-DESEMPENHO`
#: colapsou em três perfis.
COM_TETO = _constantes(R / "src/hefesto_dualsense4unix/core/rumble.py",
                       {"_ORCAMENTO_COM_TETO"})["_ORCAMENTO_COM_TETO"]

ROT_PERFIL = ORC["ROTULOS_DOS_PERFIS"]
#: O perfil que a mesa mostra escolhido. É o MESMO que a Conexões mostrava no
#: dropdown que se mudou para cá (`PERFIS[0]`, "Tudo ligado") — trocar o estado
#: no transplante faria as quatro linhas de teto por controle da Conexões
#: passarem a mentir sobre o global. O estado é dela, não meu.
PERFIL_DA_MESA = ORC["PERFIS"][0]
#: As coisas que o perfil DEVERIA alcançar, e as que ele alcança hoje. Dono
#: único no produto (`LINHAS_DO_TETO`); a tela deriva a frase em vez de repetir
#: a lista, que é a mesma cura do `alcance_de_hoje()` de lá.
ALCANCA = [linha["nome"] for linha in ORC["LINHAS_DO_TETO"] if linha["tem_ponto"]]
PENDENTES = [linha["nome"] for linha in ORC["LINHAS_DO_TETO"] if not linha["tem_ponto"]]


def teto_do_perfil(perfil):
    """O teto que um perfil da TELA impõe, ou `None` quando não há teto.

    É a conta de `core.rumble.teto_do_orcamento`, com as duas pontas lidas do
    produto: a tradução perfil->disco (`TETO_POR_PERFIL`) e o degrau
    (`RUMBLE_POLICY_MULT`). **A palavra "Sem teto" não aparece aqui** — ela saiu
    dos dois lugares onde vivia por decisão dela (D-O-SEM-TETO-SAI-DOS-DOIS-LUGARES),
    e `None` é a ausência de teto, que a frase diz com outras palavras.
    """
    chave = ORC["TETO_POR_PERFIL"][perfil]
    return None if chave != COM_TETO else MULT[COM_TETO]


def forca_do_perfil(perfil):
    """`"30% da força"`, ou `None` quando o perfil não põe teto nenhum."""
    teto = teto_do_perfil(perfil)
    return None if teto is None else f"{round(teto * 100)}% da força"


#: O perfil que é o único a pôr teto hoje — DESCOBERTO, não digitado. A frase da
#: tela está escrita no singular ("é o único que põe teto"), e por isso a
#: suposição tem de reprovar EM VOZ ALTA no dia em que deixar de valer, em vez
#: de a tela passar a afirmar sozinha uma coisa que o produto desmentiu.
_COM_TETO = [p for p in ORC["PERFIS"] if teto_do_perfil(p) is not None]
if len(_COM_TETO) != 1:
    raise SystemExit("ERRO: a frase do Perfil de Bateria afirma que UM perfil põe teto, "
                     f"e agora são {len(_COM_TETO)}: {_COM_TETO}. Reescreva a frase.")
_SO_ESTE = _COM_TETO[0]


def impoe(perfil):
    """O que o perfil escolhido impõe — o valor curto da linha de estado."""
    forca = forca_do_perfil(perfil)
    return f"Vibração em {forca}" if forca else "Nada é limitado"


# ---------------------------------------------------------------------------
# UM QUADRO SÓ, E É A NORMA DA CASA — não uma invenção desta aba.
#
# DEFEITO CURADO em 28/08/2026. A aba tinha QUATRO quadros em três fileiras e o
# miolo escondia 93px: na foto, o segundo botão do "Avançado" saía fatiado ao
# meio e o painel de registro mostrava UMA linha das quatro.
#
# A conta que explica o defeito, medida no Chrome:
#
#   • o miolo tem 542px, dos quais 508 de conteúdo (34 de padding);
#   • cada quadro custa 54px SÓ de moldura — 28 do `quadro-topo`, 24 do padding
#     do corpo, 2 de borda —, mais 14px de vão entre fileiras;
#   • quatro quadros em três fileiras = 190px de moldura para 411px de conteúdo.
#     411 + 190 + 34 = 635, e a janela tem 542.
#
# Espremer o conteúdo não fecha essa conta: com TODA linha no seu mínimo (botão
# colado em botão, rótulo sem respiro) as três fileiras ainda somavam ~550. O
# que sobra na conta é a MOLDURA REPETIDA, e é ela que sai.
#
# E a saída não é invenção: das dez abas, sete têm UM quadro só, com o nome da
# aba no título e as seções por dentro (`sec-rot`, como a Navegação e a
# Vibração). As duas que fugiam disso — esta e a Conexões — eram exatamente as
# duas que escondiam conteúdo. Aqui as quatro seções viram quatro faixas
# rotuladas dentro de um quadro só: 54px de moldura no lugar de 190, e as três
# barras de 1px continuam separando os blocos irmãos.
# ---------------------------------------------------------------------------
CSS = """
  /* ---------- Sistema, em três seções (A-09-SISTEMA-EM-TRES-SECOES-01, 25/09/2026) ----------
     Pedido dela: *«praticamente vamos só mudar de lugar as coisas dessa aba»*.
     1. Status (três colunas: o Status e o exame em duas);
     2. Configurações Avançadas (quatro colunas de botões);
     3. os Detalhes técnicos, com a altura que sobra.
     O quadro é `estica`: a seção 3 é a única que sabe crescer, e cresce. */

  /* `minmax(0,1fr)` EM TODA FAIXA — a lição de 31/08 continua valendo: `1fr` tem
     por piso o CONTEÚDO, e uma frase longa do exame empurraria a coluna vizinha
     para fora do quadro. A régua 5, lá embaixo, cobra as três. */
  .status3{display:grid;grid-template-columns:minmax(0,1fr) 1px minmax(0,2fr);
           gap:0 20px;align-items:start}
  .avancadas{display:grid;grid-template-columns:minmax(0,1fr) 1px minmax(0,1fr) 1px
             minmax(0,1fr) 1px minmax(0,1fr);gap:0 20px;align-items:start}
  .risco{background:var(--border-sutil);align-self:stretch}

  /* o rótulo de cada coluna nasce no x da coluna que ele nomeia — por isso o
     `sec-rot` repete o `grid-template-columns` da faixa que encabeça. */
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);
           margin-bottom:5px;height:17px;display:grid;gap:0 20px;align-items:center}
  .sec-rot > span{display:flex;align-items:center;gap:8px;min-width:0;white-space:nowrap}
  .sec-rot .ajuda{text-transform:none;letter-spacing:0}
  .sec-rot .conta{text-transform:none;letter-spacing:0}
  .sr-status3{grid-template-columns:minmax(0,1fr) 1px minmax(0,2fr)}
  .sr-avancadas{grid-template-columns:minmax(0,1fr) 1px minmax(0,1fr) 1px
                minmax(0,1fr) 1px minmax(0,1fr)}
  /* A LINHA DO TÍTULO DA SEÇÃO 3 LEVA O «Copiar», que é mais alto que os 17px
     de um rótulo: ela mede o que tem dentro, e a borda de cima fica nela. */
  .sr-log{grid-template-columns:minmax(0,1fr) auto;height:auto}
  /* NENHUMA FAIXA ENCOLHE — o quadro é `estica` e o corpo é uma coluna flex:
     sem isto o navegador espreme os rótulos para dar altura ao registro. Quem
     cresce e encolhe é só o `.registro`. */
  .quadro-corpo > *{flex-shrink:0}
  /* o título da seção 2 — o nome que ela deu, uma linha acima dos quatro rótulos. */
  .sec-grupo{font-size:12.5px;font-weight:600;color:var(--texto-suave);
             margin:14px 0 8px;padding-top:10px;border-top:1px solid var(--border-sutil)}
  .sec-alta{margin-top:14px;padding-top:10px;border-top:1px solid var(--border-sutil)}

  /* AS LINHAS DO STATUS E DO EXAME SÃO A MESMA PEÇA — pedido dela: *«no MESMO
     estilo das linhas do O exame de hoje (a pílula à esquerda e o texto
     curto)»*. 25,5px por linha, e quatro linhas em cada uma das três colunas:
     elas acabam no mesmo y. */
  .saude{display:flex;align-items:center;gap:9px;height:25.5px;font-size:12px;
         color:var(--texto-suave);border-bottom:1px solid var(--border-sutil);
         text-decoration:none}
  .saude:last-child{border-bottom:none}
  /* 76px E NÃO 68 — a pílula do Status diz a palavra do estado («PAUSADO»,
     «SEM VER»), e ela tem nove letras. As três colunas usam a mesma largura:
     pílula de tamanho diferente na mesma faixa seria duas peças. */
  .saude .selo{flex:0 0 76px;text-align:center}
  .selo .sg{margin-right:4px;font-weight:700}
  .selo.ok{background:var(--green);color:var(--app-bg)}
  .selo.aviso{background:var(--orange);color:var(--app-bg)}
  .selo.nt{background:var(--comment);color:var(--app-bg)}
  .saude .txt{flex:1;display:flex;align-items:center;gap:7px;min-width:0}
  .saude .txt span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .saude .ajuda .dica{left:auto;right:22px}
  /* A LINHA QUE LEVA A OUTRO LUGAR (a do Bluetooth, para a seção do rádio da
     aba Conexões) é um `<a>` inteiro: a mão vira e a linha acende no hover. */
  a.saude.vai{cursor:pointer}
  a.saude.vai:hover .txt{color:var(--fg)}
  .saude-cols{display:grid;grid-template-columns:minmax(0,1fr) 1px minmax(0,1fr);gap:0 18px}
  .col-lista{display:flex;flex-direction:column;min-width:0}

  /* AS QUATRO COLUNAS DE BOTÕES — três itens em cada, na vertical, da mesma
     altura (`--h-acao`) e com o mesmo vão: as quatro acabam no mesmo y. */
  .coluna{display:flex;flex-direction:column;gap:6px;min-width:0}
  .coluna .btn{width:100%;justify-content:center;padding:0 8px}
  /* O BOTÃO QUE SÓ NASCE NUM ESTADO — o «Corrigir o serviço» do modo
     improvisado. Fora dele sai do FLUXO (`display:none`, e não `visibility`),
     e quando aparece entra NO LUGAR do Reiniciar, que é o clique que não
     funciona nesse modo (o `+` alcança a `.acao` vizinha). */
  .so-avulso:not(.mostra){display:none}
  .so-avulso.mostra + .acao{display:none}
  /* a caixa do botão que pode ficar cinza: o `?` da razão fica na LINHA do
     botão, e a altura é a mesma nos dois estados (régua 8). */
  .acao{display:flex;align-items:center}
  .coluna .acao > .btn{flex:1;min-width:0;width:auto}
  .coluna .ajuda.porque .dica{left:auto;right:22px}
  /* O BOTÃO DO SERVIÇO TEM DUAS CORES, e quem escolhe é o produto: vermelho
     quando o clique PARA, verde quando ele DEVOLVE o serviço (a pausa ativa,
     ou ele parado). A classe `verde` é acesa pelo campo que o pacote escreve
     todo tique; a regra de baixo só a deixa vencer o vermelho. */
  .btn.vermelho.verde{color:var(--green)}
  .btn.vermelho.verde:hover{border-color:var(--green);color:var(--green)}

  /* O PERFIL GLOBAL DE BATERIA, NA VERTICAL — os três botões da aba Vibração
     (`.seg`), empilhados, na altura dos botões vizinhos. Escolha única: o aceso
     é o `on`, e o nome de cada um vem do produto. */
  .seg.bat-perfis{flex-direction:column;flex-wrap:nowrap;gap:6px}
  .seg.bat-perfis button{flex:0 0 var(--h-acao);height:var(--h-acao);min-width:0;
                         padding:0 8px;overflow:hidden;text-overflow:ellipsis;
                         white-space:nowrap}

  /* OS LIGÁVEIS SÃO A PÍLULA DO «Modo Freestyle» DA ABA JOGAR — a mesma peça
     (`aba01.py`, `.cadeado` e `.ligada`): verde e com o ponto aceso quando
     ligado, apagado quando não. O estado vem do produto, nunca do clique. */
  .cadeado{display:inline-flex;align-items:center;justify-content:center;gap:7px;
           height:var(--h-acao);width:100%;white-space:nowrap;
           border-radius:7px;padding:0 12px;font-size:12.5px;font-family:inherit;
           cursor:pointer;
           border:1px solid var(--border-forte);background:var(--app-bg);
           color:var(--texto-mudo)}
  .cadeado .p{width:7px;height:7px;border-radius:50%;flex:0 0 auto;
              background:var(--border-forte);box-shadow:none}
  .cadeado.ligada{border-color:var(--green);background:rgba(80,250,123,.09);
                  color:var(--green)}
  .cadeado.ligada .p{background:var(--green);box-shadow:0 0 6px var(--green)}

  /* OS DETALHES TÉCNICOS OCUPAM O QUE SOBRA — pedido dela: *«ganhar altura pra
     ocupar melhor esse espaço abaixo dele. e ser mais fácil de ser lido»*.
     A seção cresce com o quadro (`estica`), e a caixa é ABSOLUTA dentro dela:
     um filho absoluto não conta para a altura do pai, então o registro vivo,
     com as suas oitenta linhas, ROLA POR DENTRO em vez de empurrar a página
     (a cura da ROLAGEM-01, de 09/09, continua a mesma). O piso guarda que ela
     nunca caia abaixo de seis linhas.

     A LINHA QUEBRA, E NÃO SAI PELA DIREITA — 25/09/2026. Era `pre`, e a linha
     do journal (uns 200 caracteres) saía cortada: para ler uma linha inteira
     era preciso rolar de lado, e ela pediu o painel «mais fácil de ser lido».
     `pre-wrap` guarda as quebras do texto e dobra o que não cabe. */
  .registro{flex:1 1 auto;flex-shrink:1;min-height:120px;position:relative}
  .registro > .log{position:absolute;top:0;right:0;bottom:0;left:0}
  .log{padding:10px 12px;border:1px solid var(--border-sutil);border-radius:7px;
       background:var(--app-bg);font-family:'JetBrains Mono',monospace;font-size:11px;
       line-height:1.6;color:var(--texto-suave);overflow:auto;white-space:pre-wrap;
       overflow-wrap:anywhere}
  .sec-rot .btn.copiar{height:22px;padding:0 12px;font-size:11.5px}
""" + CSS_GLIFO


#: O ESTADO DOS TRÊS LIGÁVEIS NA CENA DO DESENHO. Nenhum deles é verdade da
#: máquina de ninguém: na tela viva quem acende é o produto, a cada tique. O
#: desenho mostra os dois estados para ela ver a pílula acesa e a apagada.
LIGAVEIS = (
    ("Iniciar com o sistema", "autostart", "hefesto-autostart", True,
     "Liga o serviço junto com o computador. Clique para trocar."),
    ("Fixar Proton", "fixar-proton", "proton-fixado", True,
     "Mantém os jogos na versão do Proton que faz o controle vibrar e tocar "
     "som. Clique para trocar, com a Steam fechada."),
    ("Corrigir Vulkan", "corrigir-vulkan", "vulkan-corrigido", False,
     "Tira dos jogos a sobreposição Vulkan que engasga a imagem. Desligar "
     "devolve o que foi tirado."),
)


def ligavel(rotulo, gesto, campo, ligado, dica):
    """A pílula que liga e desliga — a do «Modo Freestyle», com o endereço do produto."""
    return (f'            <button class="cadeado{" ligada" if ligado else ""}"'
            f' title="{dica}" data-gesto="{_gesto(gesto)}"'
            f' data-campo="{_id(campo)}" data-hef-alvo="classe"'
            f' data-hef-classe="ligada"><span class="p"></span>{rotulo}</button>')


def linha(selo, cls, g, txt, dica="", ident="", href="", title=""):
    """Uma linha do Status ou do exame — a MESMA peça, na marcação do produto.

    O produto monta as mesmas linhas em `pacotes/a09_sistema.linha_do_status`
    e `_linha_do_exame`; o desenho não pode ter uma forma que a tela viva não
    tenha, senão a primeira pintura muda a cara da aba.
    """
    tag = "a" if href else "div"
    vai = " vai" if href else ""
    i = f' data-id="{ident}"' if ident else ""
    h = f' href="{href}"' if href else ""
    t = f' title="{title}"' if title else ""
    ajuda = (f'<span class="ajuda">?<span class="dica">{dica}</span></span>'
             if dica else "")
    return (f'            <{tag} class="saude{vai}"{i}{h}>'
            f'<span class="selo {cls}"><span class="sg">{g}</span>{selo}</span>'
            f'<span class="txt"{t}><span>{txt}</span></span>{ajuda}</{tag}>')


def item(rotulo, diz, cls="btn", gesto="", em_voo="", extra=""):
    """Um botão com o que ele faz no `title` — pedido dela em 27/08.

    `em_voo` é o rótulo da espera (decisão [03] do PO, 04/09/2026): o botão diz
    que está trabalhando, no lugar exato do clique.
    """
    g = f' data-gesto="{gesto}"' if gesto else ""
    v = f' data-hef-em-voo="{em_voo}"' if em_voo else ""
    return f'''            <button class="{cls}" title="{diz}"{g}{v}{extra}>{rotulo}</button>'''


def item_escondido(rotulo, diz, gesto, campo, cls="btn"):
    """Um botão que o desenho tem e a tela só mostra quando o produto manda.

    O `campo` é o `data-campo` que o pacote escreve a cada tique — e ele escreve
    SEMPRE, inclusive vazio, que é o que faz o botão SUMIR de volta quando o
    estado passa. Ver `pacotes/a09_sistema.CAMPO_DO_MODO_AVULSO`.
    """
    return (f'            <button class="{cls} so-avulso" title="{diz}"'
            f' data-gesto="{_gesto(gesto)}" data-campo="{campo}"'
            f' data-hef-alvo="classe" data-hef-classe="mostra">{rotulo}</button>')


def item_cinza(rotulo, diz, gesto, cls=""):
    """Um botão que sabe ficar cinza, com a razão no `?` (decisão [02] do PO).

    A razão não se digita aqui: quem a conhece é `aba_sistema.travas()`, no
    produto, e ela muda a cada tique.
    """
    return ('            <div class="acao">'
            + botao_cinza(rotulo, _razao(gesto), tom=cls,
                          extra=f'data-gesto="{_gesto(gesto)}" title="{diz}"')
            + "</div>")


#: Os três botões do Perfil Global de Bateria. NENHUM nome e NENHUMA dica
#: digitados: o rótulo vem de `ROTULOS_DOS_PERFIS` e a dica de `impoe()`, que é
#: a conta do `RUMBLE_POLICY_MULT` do daemon. `data-v` é o que o CLIQUE manda
#: ao Python (o piloto encaminha `v`); `data-hef-quando` é o que a PINTURA
#: compara — as duas pontas do mesmo botão, e o teste
#: `test_o_aceso_do_perfil_de_bateria_e_dado` cobra que sejam iguais.
def _botoes_bateria():
    return "".join(
        f'<button class="{"on" if p == PERFIL_DA_MESA else ""}"'
        f' data-gesto="{_gesto("perfil-da-mesa")}" data-v="{p}"'
        f' data-campo="{_id("bateria-perfil")}" data-hef-alvo="classe"'
        f' data-hef-classe="on" data-hef-quando="{p}"'
        f' title="{ROT_PERFIL[p]}: {impoe(p).lower()}. Vale para os {N} controles —'
        f' cada um pode ter o seu na aba Conexões.">{ROT_PERFIL[p]}</button>'
        for p in ORC["PERFIS"])


# --- o Status -----------------------------------------------------------------
# A cena do desenho: o serviço ligado, a troca de perfil vendo a janela, o
# ambiente de uma máquina COSMIC e o rádio com os controles da mesa que estão
# nele. As palavras da pílula e as frases são as da camada do produto
# (`gui/aba_sistema.status_do_*`) — o teste da forma compara as duas.
_NO_RADIO = len(BT)
STATUS = [
    linha("LIGADO", "ok", "✓", "Serviço",
          "Roda por trás e volta sozinho se travar.", ident="hefesto-estado"),
    linha("LIGADO", "ok", "✓", "Troca de perfil ao abrir o jogo",
          "O perfil do jogo entra sozinho quando ele abre.",
          ident="hefesto-troca-de-perfil"),
    linha("NOTA", "nt", "i", "Ambiente gráfico: Wayland · COSMIC",
          "É por ele que o Hefesto vê qual janela está na frente.",
          ident="hefesto-ambiente"),
    linha("OK", "ok", "✓",
          f"Bluetooth: 1 adaptador · {_NO_RADIO} "
          f"{'controle' if _NO_RADIO == 1 else 'controles'}",
          "Clique para ver os adaptadores na aba Conexões.",
          ident="status-bluetooth", href="08-conexoes.html#rd-secao"),
]

# --- o exame de hoje ------------------------------------------------------------
# AS LINHAS SÃO CURTAS, E A FRASE INTEIRA FICA NO `title` — pedido dela, 25/09:
# *«Vamos simplificar cada texto, seja tooltip ou seja do doctor que aparece
# ali.»* O produto corta a frase do `doctor` na cabeça
# (`a09_sistema.frase_curta_do_exame`); o desenho mostra frases dessa forma. O
# Bluetooth SAIU daqui e foi para o Status: duas linhas dizendo a mesma coisa
# na mesma faixa seria dizer duas vezes.
ACHADOS = [
    linha("OK", "ok", "✓", "Regra de permissão dos controles instalada",
          title="Regra de permissão dos controles instalada"),
    linha("OK", "ok", "✓", "O serviço sobe sozinho no login",
          title="O serviço sobe sozinho no login"),
    linha("OK", "ok", "✓", "Steam Input desligado para o DualSense",
          title="Steam Input desligado para o DualSense"),
    linha("OK", "ok", "✓", f"Áudio dos {N} controles roteado",
          title=f"Áudio dos {N} controles roteado"),
    linha("OK", "ok", "✓", "Nenhuma sobreposição picotando o jogo",
          title="Nenhuma sobreposição picotando o jogo"),
    linha("NOTA", "nt", "i", "Um gamepad virtual por jogador",
          title="Um gamepad virtual por jogador"),
    linha("NOTA", "nt", "i", "Proton fixado em 9.0-4 para 3 jogos",
          title="Proton fixado em 9.0-4 para 3 jogos"),
    linha("NOTA", "nt", "i", "Som do sistema: sai em Controle 1",
          title="Som do sistema: sai em Controle 1"),
]
MEIO = len(ACHADOS) // 2 + len(ACHADOS) % 2

# AS DICAS DOS RÓTULOS, CURTAS — uma frase cada. O que explicava o que cada
# linha faz foi para o `?` da própria linha.
D_STATUS = ('<span class="ajuda">?<span class="dica">'
            'Como o Hefesto está agora neste computador. A pílula diz o estado.'
            '</span></span>')
D_EXAME = ('<span class="ajuda">?<span class="dica">'
           'O que costuma brigar com os controles neste computador. Passe o mouse '
           'numa linha para ler a frase inteira.'
           '</span></span>')
D_SERVICO = ('<span class="ajuda">?<span class="dica">'
             'Parar aqui não é o mesmo que desligar o Hefesto na aba Jogar: lá ele '
             'só sai do meio do jogo.'
             '</span></span>')
D_BATERIA = ('<span class="ajuda">?<span class="dica">'
             f'Vale para os {N} controles, e cada um pode ter o seu na aba Conexões.'
             '</span></span>')
D_SAUDE = ('<span class="ajuda">?<span class="dica">'
           'Consertos que o exame já faz sozinho, para repetir quando precisar.'
           '</span></span>')
D_AUTOMATICO = ('<span class="ajuda">?<span class="dica">'
                'Verde é ligado. Clique para trocar.'
                '</span></span>')
D_LOG = ('<span class="ajuda">?<span class="dica">'
         'O registro do serviço, sempre à vista. Copie para relatar um problema.'
         '</span></span>')

# O BOTÃO SE CHAMA "ATUALIZAR", E O NOME É PALAVRA DELA — 05/09/2026, a 09-Q1:
# *"Segue fazendo os dois. Com mesmo nome"*. A dica diz os dois trabalhos, e o
# `data-hef-em-voo` é o rótulo da espera (a 09-Q3).
ROTULO_ATUALIZAR = "Atualizar"
EM_VOO_ATUALIZAR = "Atualizando…"
DICA_ATUALIZAR = ("Manda o serviço reler os atalhos do controle e os arquivos "
                  "que a Steam usa para abrir os jogos. Leva alguns segundos.")

#: O BOTÃO DO SERVIÇO NA CENA DO DESENHO: o serviço de pé e sem pausa, que é o
#: estado de quase sempre — por isso ele diz «Parar o serviço», vermelho. Com a
#: pausa ativa o produto o troca por «Retomar» (verde), e com o serviço parado
#: por «Ativar o serviço» (verde) — `a09_sistema._rotulo_de_agora`.
ROTULO_PARAR = "Parar o serviço"

MIOLO = f'''
    <div class="quadro estica">
      <div class="quadro-topo">
        <span class="quadro-titulo">Sistema</span>
        <span class="ajuda">?<span class="dica">
          Esta aba é sobre o computador, não sobre um controle. Por isso a fita de controles
          está apagada aqui.
        </span></span>
      </div>
      <div class="quadro-corpo">

        <!-- ---------- 1. STATUS + O EXAME DE HOJE ---------- -->
        <div class="sec-rot sr-status3">
          <span>Status {D_STATUS}</span><span></span>
          <span>O exame de hoje {D_EXAME}
            <span class="conta" data-id="{_id("exame-contagem")}" data-campo="{_id("exame-contagem")}" data-hef-alvo="html">{len(ACHADOS)} linhas <span class="sep">·</span> nenhum aviso</span></span>
        </div>
        <div class="status3">
          <div class="col-lista" data-id="{_id(CAMPO_DO_STATUS)}" data-campo="{_id(CAMPO_DO_STATUS)}" data-hef-alvo="html">
{chr(10).join(STATUS)}
          </div>
          <div class="risco"></div>
          <div class="saude-cols" data-id="{_id("exame-lista")}" data-campo="{_id("exame-lista")}" data-hef-alvo="html">
            <div class="col-lista">
{chr(10).join(ACHADOS[:MEIO])}
            </div>
            <div class="risco"></div>
            <div class="col-lista">
{chr(10).join(ACHADOS[MEIO:])}
            </div>
          </div>
        </div>

        <!-- ---------- 2. CONFIGURAÇÕES AVANÇADAS ---------- -->
        <div class="sec-grupo">Configurações Avançadas</div>
        <div class="sec-rot sr-avancadas">
          <span>Serviço {D_SERVICO}</span><span></span>
          <span>Perfil Global de Bateria {D_BATERIA}</span><span></span>
          <span>Saúde do App {D_SAUDE}</span><span></span>
          <span>Automático {D_AUTOMATICO}</span>
        </div>
        <div class="avancadas">
          <div class="coluna col-servico">
{item(ROTULO_PARAR, "O Hefesto deixa de rodar e os controles viram gamepads comuns. Pergunta antes.", "btn vermelho", gesto=_gesto("parar-ou-retomar"), extra=f' data-campo="{CAMPO_DO_VERDE}" data-hef-alvo="classe" data-hef-classe="verde"')}
{item(ROTULO_ATUALIZAR, DICA_ATUALIZAR, gesto=_gesto("atualizar"), em_voo=EM_VOO_ATUALIZAR)}
{item_escondido("Corrigir o serviço", "O serviço está rodando por fora do sistema, e ali reiniciar não funciona. Este botão o faz subir do jeito certo.", "corrigir-modo", CAMPO_DO_MODO_AVULSO)}
{item_cinza("Reiniciar", "Para e liga de novo o serviço. Resolve a maioria dos travamentos, e nenhum ajuste seu se perde.", "reiniciar")}
          </div>
          <div class="risco"></div>
          <div class="coluna">
            <div class="seg bat-perfis" data-id="{_id("bateria-perfil")}">{_botoes_bateria()}</div>
          </div>
          <div class="risco"></div>
          <div class="coluna">
{item("Reaplicar correções automáticas", "Desliga o Steam Input onde ele atrapalha. Sem senha, sem fechar nada, e com cópia de segurança.", gesto=_gesto("refazer-consertos"))}
{item("Aplicar soluções nos lançadores", "Põe a linha do Hefesto nos jogos da Steam, sem perder as suas opções. Pergunta antes: fecha a Steam por uns 20 segundos.", gesto=_gesto("aplicar-aos-jogos"))}
{item("Restaurar de fábrica", "Devolve o perfil de fábrica. Pergunta antes, e os seus perfis salvos ficam.", "btn vermelho", gesto=_gesto("restaurar-de-fabrica"))}
          </div>
          <div class="risco"></div>
          <div class="coluna col-ligaveis">
{chr(10).join(ligavel(*x) for x in LIGAVEIS)}
          </div>
        </div>

        <!-- ---------- 3. DETALHES TÉCNICOS ---------- -->
        <div class="sec-rot sr-log sec-alta">
          <span>Detalhes técnicos {D_LOG}</span>
          <span>{item("Copiar", "Copia o registro inteiro para colar num relato.", "btn copiar", gesto=_gesto("copiar-registro")).strip()}</span>
        </div>
        <div class="registro">
          <div class="log" data-id="{_id("registro-texto")}" data-campo="{_id("registro-texto")}" data-hef-rolar="fim">[23:41:02] daemon pronto · {N} controles · {N} gamepads virtuais · controle virtual ok
[23:41:02] {" · ".join(f'p{c["jogador"]} {c["via"].lower()}' for c in MESA)} · fw 0x0356 nos {N} · cor de fábrica lida ({", ".join(f'p{c["jogador"]}' for c in CONECTADOS)})
[23:41:07] exame: steam input desligado em 2 jogos · proton 9.0-4 fixado em 3
[23:41:09] perfil "Mortal Kombat" aplicado aos {N} · gatilho L2 escrito, sem leitura de volta
[23:41:12] rádio: 1 adaptador · {_NO_RADIO} {'controle' if _NO_RADIO == 1 else 'controles'} · sem fila
[23:41:15] janela da frente: steam_app_1971870 · perfil "Mortal Kombat" mantido</div>
        </div>

      </div>
    </div>
'''

LEGENDA = '''<div class="nota">
  <h2>A aba Sistema em três seções — 25/09/2026</h2>
  <ul>
    <li><b>O pedido dela:</b> <i>"praticamente vamos só mudar de lugar as coisas dessa aba"</i>,
      com menos texto e mais gesto. <!-- noqa-acento: citação literal dela --></li>
    <li><b>1. Status</b> — o antigo <i>O serviço</i> virou <b>Status</b>, com quatro linhas na
      forma do exame (a pílula e o texto curto): <b>Serviço</b> (LIGADO, PAUSADO ou PARADO — a
      pausa deixou de ter linha própria), <b>Troca de perfil</b>, <b>Ambiente gráfico</b> e
      <b>Bluetooth</b>, que leva à seção do rádio da aba Conexões. O exame fica ao lado, em duas
      colunas, e o Bluetooth saiu dele. As frases do exame saem curtas; a inteira fica no
      <code>title</code>.</li>
    <li><b>2. Configurações Avançadas</b> — quatro colunas: <b>Serviço</b> (Parar/Retomar num botão
      só, Atualizar, Reiniciar), <b>Perfil Global de Bateria</b> (as três escolhas na vertical),
      <b>Saúde do App</b> (Reaplicar correções automáticas, Aplicar soluções nos lançadores,
      Restaurar de fábrica) e <b>Automático</b> (Iniciar com o sistema, Fixar Proton, Corrigir
      Vulkan — a pílula do Modo Freestyle, verde quando ligada).</li>
    <li><b>3. Detalhes técnicos</b> — sempre à vista, com o registro do serviço, a altura que sobra
      e um <b>Copiar</b>. O <i>Ver detalhes</i> deixou de existir.</li>
    <li><b>Saíram</b>: a chave <i>Ligar junto com o computador</i> do topo (virou o ligável
      <i>Iniciar com o sistema</i>) e as quatro linhas de baixo do Perfil de Bateria (Limite, Vale
      para, Com limite, Sem limite).</li>
  </ul>
</div>

</body>
</html>
'''

# ---------------------------------------------------------------------------
# AS RÉGUAS DO GERADOR — elas rodam no IMPORT e leem `MIOLO`, que é memória:
# `import aba09` reprova um desenho quebrado sem tocar em disco nenhum.
#
# A FORMA MUDOU EM 25/09/2026 (A-09-SISTEMA-EM-TRES-SECOES-01). Cada régua que
# media a forma velha acompanha a nova; a que perdeu o objeto sai com a razão
# numa linha no lugar dela.
# ---------------------------------------------------------------------------
def _medida(texto, regra, prop):
    """`height:30px` de dentro de uma regra de CSS — lido, nunca digitado."""
    bloco = re.search(re.escape(regra) + r"\{([^}]*)\}", texto)
    if not bloco:
        raise SystemExit(f"ERRO: a regra CSS `{regra}` sumiu — a régua das "
                         "colunas mede por ela.")
    px = re.search(prop + r":(\d+(?:\.\d+)?)px", bloco.group(1))
    if not px:
        raise SystemExit(f"ERRO: `{regra}` não declara mais `{prop}` em px.")
    return float(px.group(1))


def _token(texto, nome):
    """`--h-acao:34px` do esqueleto — lido pelo TOKEN, não pelo bloco."""
    px = re.search(re.escape(nome) + r":(\d+(?:\.\d+)?)px", texto)
    if not px:
        raise SystemExit(f"ERRO: o esqueleto não declara mais `{nome}` em px — "
                         "a régua das colunas mede por ele.")
    return float(px.group(1))


def _entre(html, de, ate):
    i = html.index(de) + len(de)
    return html[i:html.index(ate, i)]


_TOPO = (pathlib.Path(__file__).parent / "topo.html").read_text()
H_ACAO = _token(_TOPO, "--h-acao")                     # botão de ação

# O PORTÃO DOS DOIS BLOCOS DA PRIMEIRA FAIXA (31/08/2026) SAIU: o Perfil de
# Bateria e «O serviço» deixaram de ser blocos irmãos — os dois viraram colunas
# da seção 2, e a promessa deles («acabam no mesmo y») é a régua A, abaixo.

# A. AS QUATRO COLUNAS DA SEÇÃO 2 ACABAM NO MESMO y — e as três da seção 1.
#    Conta o que ocupa linha em cada coluna (o botão escondido do modo
#    improvisado não conta, e a exclusão é amarrada à regra de CSS que o
#    esconde) e exige a MESMA conta e a MESMA altura por item. Uma coluna com um
#    botão a mais é o vão de 58px que ela apontou em 31/08, de outro jeito.
_ESCONDE_O_AVULSO = ".so-avulso:not(.mostra){display:none}" in CSS
_COLUNAS = re.findall(r'<div class="coluna[^"]*">(.*?)\n          </div>\n',
                      _entre(MIOLO, '<div class="avancadas">', "3. DETALHES"), re.S)
if len(_COLUNAS) != 4:
    raise SystemExit(f"ERRO: a seção Configurações Avançadas tem {len(_COLUNAS)} "
                     "colunas e ela pediu quatro — ou a régua deixou de achá-las.")
_ITENS = []
for _col in _COLUNAS:
    _n = _col.count("<button")
    _fora = _col.count("so-avulso")
    if _fora and not _ESCONDE_O_AVULSO:
        raise SystemExit("ERRO: há botão `so-avulso` e a folha não o esconde mais — "
                         "ele passaria a ocupar linha na cena que ela aprovou.")
    _ITENS.append(_n - _fora)
if len(set(_ITENS)) != 1:
    raise SystemExit(f"ERRO: as quatro colunas das Configurações Avançadas têm "
                     f"{_ITENS} itens à vista — elas deixam de acabar no mesmo y. "
                     "Ela pediu três em cada, na vertical.")
for _regra in (".seg.bat-perfis button", ".cadeado"):
    _alt = re.search(re.escape(_regra) + r"\{[^}]*height:var\(--h-acao\)", CSS)
    if not _alt:
        raise SystemExit(f"ERRO: `{_regra}` deixou de medir `--h-acao` — a coluna "
                         "dela deixa de acabar no mesmo y das vizinhas.")
if len(STATUS) != MEIO:
    raise SystemExit(f"ERRO: o Status tem {len(STATUS)} linhas e cada coluna do "
                     f"exame tem {MEIO} — as três colunas da seção 1 deixam de "
                     "acabar no mesmo y.")

# B. O PORTÃO DA PALAVRA — 31/08/2026, e ele guarda uma decisão DELA: «Hefesto»
#    ficou com a aba Jogar, onde nomeia o MODO; aqui o rótulo nomeia o SERVIÇO.
#    Ele olha SÓ o que a pessoa lê como nome (o rótulo da coluna, a linha do
#    Status e os botões da coluna do serviço); o `title` PODE dizer Hefesto.
_ACOES_DO_SERVICO = _entre(MIOLO, '<div class="coluna col-servico">', '<div class="risco">')
_ROTULOS = {
    "a coluna": re.search(r'<div class="sec-rot sr-avancadas">\s*<span>([^<]*)<',
                          MIOLO).group(1),
    "a linha do Status": re.search(
        r'data-id="hefesto-estado"[^>]*>.*?<span class="txt"><span>([^<]*)</span>',
        MIOLO, re.S).group(1),
}
for _i, _b in enumerate(re.findall(r">([^<>]*)</button>", _ACOES_DO_SERVICO)):
    _ROTULOS[f"o botão {_i + 1}"] = _b
if not _ROTULOS.get("o botão 1"):
    raise SystemExit("ERRO: o portão da palavra não achou botão nenhum na coluna do "
                     "serviço — a régua deixou de saber onde olhar.")
_RECAIDA = {onde: t.strip() for onde, t in _ROTULOS.items() if "Hefesto" in t}
if _RECAIDA:
    raise SystemExit(
        "ERRO: " + " · ".join(f"{onde} diz {t!r}" for onde, t in _RECAIDA.items())
        + " — e nesta aba o rótulo nomeia o SERVIÇO, não o Hefesto. A palavra "
        '"Hefesto" ficou com a aba Jogar por decisão dela (31/08/2026). O `title` '
        "do botão PODE dizer Hefesto — é lá que a diferença se explica.")

# 1. NENHUMA LINHA SEM GLIFO NA PÍLULA. Era sobre a `.est` (a chave do autostart
#    montada à mão, sem glifo); a linha de estado virou a do exame, e a régua
#    vai junto: toda pílula carrega símbolo E cor, para quem não distingue verde
#    de laranja ler o estado pelo desenho.
_SEM_GLIFO = re.findall(r'<span class="selo [a-z]+"><span class="sg">\s*</span>([^<]*)',
                        MIOLO)
_PILULAS = MIOLO.count('<span class="selo ')
if not _PILULAS:
    raise SystemExit("ERRO: nenhuma pílula no Status nem no exame — a régua do glifo "
                     "cegou, e seletor que casa ZERO é erro, não silêncio.")
if _SEM_GLIFO:
    raise SystemExit("ERRO: pílula sem glifo: " + " · ".join(repr(r) for r in _SEM_GLIFO))

# 2. OS LIGÁVEIS TÊM A PEÇA INTEIRA. Era a coerência da chave «Ligar junto com
#    o computador» (chave, glifo e classe saindo de um lugar só); a chave virou
#    o ligável «Iniciar com o sistema», e a régua cobra os três: o gesto (o
#    clique CHEGA), o endereço com alvo `classe` e `ligada` (o PRODUTO acende),
#    e o aceso do desenho igual ao que `LIGAVEIS` declara — nada digitado à mão.
_PILULAS_LIGAVEIS = re.findall(r'<button class="cadeado( ligada)?"[^>]*>', MIOLO)
if len(_PILULAS_LIGAVEIS) != len(LIGAVEIS):
    raise SystemExit(f"ERRO: a coluna Automático tem {len(_PILULAS_LIGAVEIS)} "
                     f"ligáveis e o desenho declara {len(LIGAVEIS)}.")
for _rot, _g, _c, _lig, _d in LIGAVEIS:
    _tag = re.search(r'<button class="cadeado[^"]*"[^>]*data-gesto="' + re.escape(_g)
                     + r'"[^>]*>', MIOLO)
    if not _tag:
        raise SystemExit(f"ERRO: o ligável {_rot!r} perdeu o gesto `{_g}`.")
    for _exigido in (f'data-campo="{_c}"', 'data-hef-alvo="classe"',
                     'data-hef-classe="ligada"'):
        if _exigido not in _tag.group(0):
            raise SystemExit(f"ERRO: o ligável {_rot!r} perdeu `{_exigido}` — sem "
                             "ele o estado da tela deixa de vir do produto.")
    if (" ligada" in _tag.group(0)) != _lig:
        raise SystemExit(f"ERRO: o ligável {_rot!r} nasce "
                         f"{'aceso' if ' ligada' in _tag.group(0) else 'apagado'} "
                         "e `LIGAVEIS` diz o contrário.")

# 3. OS TRÊS BOTÕES DO PERFIL DE BATERIA, e o rótulo que ela mandou tirar.
_BOTOES_BAT = re.findall(r'<button class="(on)?"[^>]*data-v="([^"]+)"[^>]*>([^<]+)</button>',
                         _entre(MIOLO, '<div class="seg bat-perfis"', "</div>"))
if len(_BOTOES_BAT) != len(ORC["PERFIS"]):
    raise SystemExit(f"ERRO: o Perfil de Bateria tem {len(_BOTOES_BAT)} botões e o produto "
                     f"declara {len(ORC['PERFIS'])} perfis — a tela deixou de mostrar todos.")
for _on, _p, _rot in _BOTOES_BAT:
    if _rot != ROT_PERFIL[_p]:
        raise SystemExit(f"ERRO: o botão de {_p!r} diz {_rot!r} e o produto o chama de "
                         f"{ROT_PERFIL[_p]!r} — nome de perfil não se digita nesta tela.")
if sum(1 for on, _, _ in _BOTOES_BAT if on) != 1:
    raise SystemExit("ERRO: a escolha do Perfil de Bateria não é única — ela pediu "
                     '"três botões lado a lado com escolha única".')
if '<span class="rot">O perfil da mesa' in MIOLO:
    raise SystemExit('ERRO: o rótulo "O perfil da mesa" voltou (ponto 7.1 dela).')

# 4. (O valor da linha de estado ancorado à direita) SAIU: a `.est` saiu da aba
#    — o Status usa a linha do exame, que não tem coluna de valor.

# 5. NENHUMA FAIXA PODE ESTOURAR. `1fr` tem por piso o tamanho do conteúdo;
#    `minmax(0,1fr)` é o que deixa a coluna encolher.
for _faixa in (".status3", ".avancadas", ".saude-cols"):
    _r = re.search(re.escape(_faixa) + r"\{[^}]*grid-template-columns:([^;]*);", CSS)
    if not _r:
        raise SystemExit(f"ERRO: a faixa `{_faixa}` sumiu ou deixou de declarar colunas — "
                         "a régua do estouro ficou cega.")
    if re.search(r"(^|\s)[12]fr", _r.group(1)):
        raise SystemExit(f"ERRO: a faixa `{_faixa}` voltou a usar `fr` cru: "
                         f"`{_r.group(1).strip()}`. O piso é o CONTEÚDO, e a coluna "
                         "sai do limite da janela. Use `minmax(0,1fr)`.")

# 6. (O nome da linha de estado fora do verde) SAIU com a `.est`: na linha do
#    exame o verde é da PÍLULA, e o texto é `--texto-suave`.

# 7. O BOTÃO CINZA TEM A PEÇA INTEIRA — decisão [02], 04/09/2026. O «Retomar»
#    deixou de ser um botão (virou uma cara do botão do serviço), e fica o
#    Reiniciar.
_CINZAS = ("reiniciar",)
for _g in _CINZAS:
    _campo = f"{_g}{SUFIXO_DA_RAZAO}"
    _btn = re.search(
        r'<button class="[^"]*"[^>]*data-campo="' + re.escape(_campo) + r'"[^>]*>',
        MIOLO)
    if not _btn:
        raise SystemExit(f"ERRO: o botão de {_g!r} perdeu o endereço `{_campo}`.")
    for _exigido in ('data-hef-alvo="classe"', 'data-hef-classe="apagado"',
                     'data-hef-atributo="aria-disabled"', f'data-gesto="{_g}"'):
        if _exigido not in _btn.group(0):
            raise SystemExit(f"ERRO: o botão de {_g!r} perdeu `{_exigido}` — a peça "
                             "da D-03 é inteira.")
    if not re.search(r'<span class="dica" data-campo="' + re.escape(_campo)
                     + r'" data-hef-alvo="html">', MIOLO):
        raise SystemExit(f"ERRO: o `?` de {_g!r} não recebe `{_campo}` pelo alvo `html`.")

# 8. O `?` DA RAZÃO NÃO PODE VIRAR FILEIRA — ele mora na `.acao`, na linha do botão.
_PORQUES = MIOLO.count('class="ajuda porque"')
_PORQUES_NA_CAIXA = sum(
    _bloco.count('class="ajuda porque"')
    for _bloco in re.findall(r'<div class="acao">.*?</div>\s*</div>', MIOLO, re.S))
if len(_CINZAS) != _PORQUES or _PORQUES_NA_CAIXA != _PORQUES:
    raise SystemExit(
        f"ERRO: esta página tem {_PORQUES} `?` de razão e {_PORQUES_NA_CAIXA} "
        f"deles dentro de uma `.acao` (esperados {len(_CINZAS)} nos dois).")

# 9. O BOTÃO DO `daemon.reload` SE CHAMA "ATUALIZAR" PORQUE ELA MANDOU (09-Q1),
#    fala durante a espera (09-Q3) e a dica não nega o trabalho caro. A palavra
#    dela entra LITERAL: comparar com a constante seria a régua apontando para si.
_RELOAD = re.search(r'<button class="btn"([^>]*)>([^<]*)</button>', "".join(
    linha_ for linha_ in _ACOES_DO_SERVICO.splitlines()
    if 'data-gesto="atualizar"' in linha_))
if not _RELOAD:
    raise SystemExit("ERRO: o botão do `atualizar` sumiu da coluna do serviço — "
                     "seletor que casa ZERO é erro, não silêncio.")
_ATRS, _ROT_RELOAD = _RELOAD.group(1), _RELOAD.group(2)
_PALAVRA_DELA_09Q1 = "Atualizar"
if ROTULO_ATUALIZAR != _PALAVRA_DELA_09Q1 or _ROT_RELOAD != _PALAVRA_DELA_09Q1:
    raise SystemExit(
        f"ERRO: o botão do `daemon.reload` diz {_ROT_RELOAD!r} e ela mandou manter "
        f"{_PALAVRA_DELA_09Q1!r} (09-Q1, 05/09/2026).")
if f'data-hef-em-voo="{EM_VOO_ATUALIZAR}"' not in _ATRS:
    raise SystemExit(f"ERRO: o botão {ROTULO_ATUALIZAR!r} perdeu o `data-hef-em-voo` (09-Q3).")
if "Não muda nada" in _ATRS:
    raise SystemExit("ERRO: a dica do `daemon.reload` voltou a dizer 'Não muda nada' — "
                     "é falso: ele relê os atalhos e reescreve o ambiente da Steam.")

# 10. O BOTÃO DO SERVIÇO É UM SÓ E TEM AS DUAS CORES — pedido dela, 25/09/2026:
#     «Retomar/Parar (um botão só, que alterna)». O vermelho é do desenho; o
#     verde é o produto quem acende, pelo campo do pacote.
_PARAR = re.search(r'<button class="btn vermelho"[^>]*data-gesto="parar-ou-retomar"[^>]*>',
                   _ACOES_DO_SERVICO)
if not _PARAR:
    raise SystemExit("ERRO: o botão Parar/Retomar sumiu da coluna do serviço.")
for _exigido in (f'data-campo="{CAMPO_DO_VERDE}"', 'data-hef-alvo="classe"',
                 'data-hef-classe="verde"'):
    if _exigido not in _PARAR.group(0):
        raise SystemExit(f"ERRO: o botão Parar/Retomar perdeu `{_exigido}` — ele "
                         "ficaria vermelho dizendo «Retomar».")
if ".btn.vermelho.verde{" not in CSS:
    raise SystemExit("ERRO: a regra que deixa o verde vencer o vermelho sumiu.")
if 'data-gesto="ver-detalhes"' in MIOLO or 'data-gesto="retomar"' in MIOLO:
    raise SystemExit("ERRO: o «Ver detalhes» ou o «Retomar» separado voltaram — ela "
                     "pediu o registro sempre à vista e um botão só para parar e retomar.")


CAMPO_DA_FITA = "fita-chips"
CAMPO_DO_CHIP = "fita-chip"


def escrever_a_bancada():
    """Monta a página e a GRAVA em `mockup/09-sistema.html`. Só do `__main__`.

    ELA ESTAVA SOLTA NO MÓDULO ATÉ 06/09/2026, e o preço era de EFEITO: um
    `import aba09` — o do teste que só quer uma constante, o da coleta do
    pytest — reescrevia a bancada DELA no disco, com o estado vivo da mesa
    dentro. Medido na costura desta leva com a irmã `aba05`: bastou COLETAR um
    teste que a importava no topo para `mockup/05-vibracao.html` mudar no disco.
    Oito dos dez geradores estavam assim; a forma certa é a da `aba01.py`.

    AS RÉGUAS 1 A 9 CONTINUAM NO IMPORT, e é de propósito: elas leem `MIOLO`,
    que é memória, e são o que faz `import aba09` reprovar um desenho quebrado
    sem tocar em disco nenhum. O que desce para cá é só quem ESCREVE.
    """
    n = monta("09-sistema", "Sistema", MIOLO, CSS, legenda=LEGENDA)

    # ---------------------------------------------------------------------------
    # O ENDEREÇO DA FITA, POSTO NA SAÍDA — 03/09/2026, a lei dela:
    #
    #     "se no topo tá mostrando controle white player 1, então cada aba vai usar
    #      os controles lá de cima. Não mistura com a info dos mockups."
    #
    # A fita inteira sai de `monta.fita()`, que é o dono dela nas DEZ páginas e não
    # é território desta aba. É a mesma situação que a `aba06.py` já resolve assim
    # desde 28/08 — *"trocado na saída, porque o texto mora no esqueleto (topo.html)
    # e esta aba só pode mexer no arquivo dela"*.
    #
    # O QUE ISTO NÃO É: maquiagem. `data-campo` sem escritor zera a régua da
    # identidade e deixa a tela mentindo igual — trocaria um congelado por um vazio.
    # Quem escreve neste endereço é `pacotes/a09_sistema.py`, e o par de nomes tem
    # régua: `test_aba09_a_fita_vem_de_cima.py` reprova se os dois arquivos
    # divergirem.
    #
    # NENHUM PIXEL MUDA. `data-campo` e `data-hef-alvo` estão nos INVISIVEIS do
    # `check_o_desenho_aprovado.py`, que compara o que se VÊ — decisão dela em
    # 01/09: *"ok, pode comparar então o que se vê."*
    # ---------------------------------------------------------------------------
    p = onde.pagina("09-sistema.html")
    s = p.read_text()

    # A ÂNCORA EXIGE A CLASSE INTEIRA. `'<div class="fita'` cru casa PRIMEIRO com
    # `<div class="fita-linha">`, o invólucro que também guarda o Perfil ativo — e
    # endereçar o invólucro com alvo `html` mandaria o produto reescrever o miolo
    # dele a cada tique, apagando o `data-campo="perfil"` do cabeçalho, que é das
    # dez abas. Aconteceu na primeira execução deste bloco, em 03/09/2026.
    abre = re.search(r'<div class="fita[ "][^>]*>', s)
    if not abre:
        raise SystemExit("ERRO: a `.fita` sumiu do esqueleto — o endereço da fita "
                         "ficou sem onde pousar, e a aba volta a mostrar o desenho.")
    fim = s.index("</div>", abre.start()) + len("</div>")
    bloco = s[abre.start():fim]

    novo = bloco.replace(
        abre.group(0),
        f'{abre.group(0)[:-1]} data-campo="{CAMPO_DA_FITA}" data-hef-alvo="html">',
        1)
    # O ENDEREÇO DO CHIP É DO `monta.fita()`, E ESTE BLOCO SÓ CONFERE — 03/09/2026.
    #
    # ELE ESCREVIA O `data-campo` DO CHIP, E O ESQUELETO PASSOU A ESCREVÊ-LO
    # TAMBÉM (`interface/monta.py:582`). Como este arquivo não foi rodado depois
    # daquela mudança, o defeito ficou latente: a primeira regeração da aba saiu com
    # `data-campo="fita-chip" data-campo="fita-chip"` nos dois chips — atributo
    # repetido, que o navegador aceita calado ignorando o segundo. Medido aqui, na
    # primeira execução do gerador nesta frente.
    #
    # O CHIP `Todos` CONTINUA DE FORA, e agora é o `monta` quem o deixa de fora: ele
    # não é aparelho nenhum, não traz cor nem nome de plástico, e endereço morto é o
    # defeito que esta leva existe para não repetir.
    #
    # A CONTA FICA. Ela é a régua da forma da fita: se o esqueleto deixar de
    # endereçar os chips, ou passar a endereçar o `Todos`, o número deixa de casar
    # com a mesa e o gerador reprova em voz alta em vez de gravar uma fita muda.
    quantos = novo.count(f'data-campo="{CAMPO_DO_CHIP}"')
    if len(CONECTADOS) != quantos:
        raise SystemExit(f"ERRO: o esqueleto endereçou {quantos} chips e a mesa tem "
                         f"{len(CONECTADOS)} conectados — a forma da fita mudou. "
                         f"O dono do `data-campo=\"{CAMPO_DO_CHIP}\"` é "
                         "`interface/monta.fita()`; esta aba só confere.")
    onde.gravar("09-sistema.html", s[:abre.start()] + novo + s[fim:])

    print(f"09-sistema: OK, {n} divs · a faixa do serviço: "
          + " · ".join(f"{t.strip()!r}" for t in _ROTULOS.values()))


if __name__ == "__main__":
    import os
    import shutil
    import tempfile

    # CONFERE ANTES DE ESCREVER — 13/09/2026. A página nasce numa bancada
    # PROVISÓRIA e só vai para a de verdade se passar; a razão e a régua estão
    # no fim do `aba04.py`.
    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-09-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    escrever_a_bancada()
    shutil.copyfile(_prova / "09-sistema.html", _real / "09-sistema.html")
    shutil.rmtree(_prova)
