import ast
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from monta import MESA, glifo, monta, CSS_GLIFO  # noqa: E402

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA. Medido em 28/08/2026: oito
# arquivos desta casa cravavam o caminho absoluto da árvore DELA, e por isso
# rodar uma CÓPIA do gerador REESCREVIA o mockup dela. Aconteceu numa prova:
# o `05-vibracao.html` dela ficou com `--r-motor:56px` porque um agente rodou
# uma cópia noutro diretório. É o mesmo estrago de 25/08, quando o mockup que
# ela ia abrir sumiu do disco na frente dela — e é o que impediria qualquer
# segunda árvore de trabalhar sem tocar na primeira.
R = pathlib.Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# A MESA MANDA NOS NÚMEROS DESTA ABA.
#
# Nada aqui digita "quatro". A aba Sistema é, do começo ao fim, uma CONTAGEM —
# quantos aparelhos existem, quantos o Hefesto criou, quantos o jogo enxerga —
# e uma contagem digitada é a que diverge no dia em que a mesa muda. Foi assim
# que o cabeçalho dizia "2 controles" com quatro chips na fita, em 27/08.
# ---------------------------------------------------------------------------
N = len(MESA)
USB = [c for c in MESA if c["via"] == "USB"]
BT = [c for c in MESA if c["via"] == "BT"]
#: Nós de `/dev/input/js*`: cada DualSense publica DOIS (o gamepad e os sensores
#: de movimento — é o `uniq` que os colapsa num aparelho só, em
#: `emulation_actions._chave_do_aparelho`), e cada gamepad virtual publica um.
NOS = 2 * N + N


#: MEDIDO no Chrome (1920×1080) com o `olhar.py` desta pasta, 28/08/2026 — e é
#: número de FOTO: mexeu no miolo, meça de novo antes de repetir a frase.
#: O miolo desta janela tem `MIOLO_H` de altura útil; o conteúdo da aba mede
#: `ALTURA`. Enquanto `ALTURA <= MIOLO_H`, nada rola por dentro e nada é fatiado.
MIOLO_H, ALTURA = 544, 542


def _lista(nomes):
    """`a`, `b` e `c` — em português, com "e" antes do último."""
    return nomes[0] if len(nomes) == 1 else f"{', '.join(nomes[:-1])} e {nomes[-1]}"


def _frase(nomes):
    """A mesma lista, em CAIXA DE FRASE: só a primeira letra é maiúscula.

    Regra dela, 30/08: *"a maiúscula a regra é sobre a primeira letra a ser
    capitalizada"*. `LINHAS_DO_TETO` guarda cada nome capitalizado porque lá
    cada um é um TÍTULO de linha; enroladas num valor de campo só, elas viram
    uma frase — e "Gatilhos, Barra de luz e Giroscópio" tem três maiúsculas no
    meio de uma. Nenhum dos nomes é próprio, caminho ou sigla, então nenhum
    perde forma ao descer. Derivado, nunca digitado: o dono continua sendo o
    produto.
    """
    return _lista([nomes[0]] + [n[0].lower() + n[1:] for n in nomes[1:]])


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
  /* ---------- Sistema ---------- */

  /* AS FAIXAS. Cada uma é [bloco | barra de 1px | bloco], e o rótulo de cada
     coluna nasce EXATAMENTE no x da coluna que ele nomeia — por isso o
     `sec-rot` repete o `grid-template-columns` da faixa que encabeça. */
  .par2{display:grid;grid-template-columns:1fr 1px 1fr;gap:0 20px;align-items:stretch}
  .exame{display:grid;grid-template-columns:1fr 1px 246px;gap:0 20px;align-items:stretch}
  .avancado{display:grid;grid-template-columns:246px 1px 1fr;gap:0 20px;align-items:stretch}
  .risco{background:var(--border-sutil)}

  /* A CAIXA ALTA SAIU — 30/08/2026. A regra desta casa sobre maiúscula é a
     PRIMEIRA LETRA, e ela confirmou: *"a maiúscula a regra é sobre a primeira
     letra a ser capitalizada, é o padrão do projeto"*. O `text-transform:
     uppercase` a violava calado, e ainda cobrava o preço de legibilidade que
     ela apontou (*"essa fonte tem um contraste horrível"*): caixa alta a 11px
     é a forma mais difícil de ler que existe.
     O `letter-spacing` sai junto — ele existia para abrir a caixa alta.
     O texto-fonte já está em caixa de frase ("Força da vibração", "Selecione o
     player"), então nada precisou ser reescrito. */
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);
           margin-bottom:5px;height:17px;display:grid;gap:0 20px;align-items:center}
  .sec-rot > span{display:flex;align-items:center;gap:8px;min-width:0;white-space:nowrap}
  .sec-rot .ajuda{text-transform:none;letter-spacing:0}
  .sec-rot .conta{text-transform:none;letter-spacing:0}
  .sr-par2{grid-template-columns:1fr 1px 1fr}
  .sr-exame{grid-template-columns:1fr 1px 246px}
  .sr-avancado{grid-template-columns:246px 1px 1fr}
  /* o respiro entre uma faixa e o rótulo da seguinte. `margin-top` na faixa e
     não `justify-content` no corpo: a cura de um vão é na altura. */
  .sec-alta{margin-top:10px}

  /* ---------------------------------------------------------------------
     ESTADO À ESQUERDA, BARRA DE 1px, AÇÃO À DIREITA — nas três faixas.
     Pedido dela em 27/08: "na aba Sistemas temos os status acima e os botões
     abaixo. Podemos mandar esses botões pra direita e ocupando o mesmo espaço
     vertical."
     --------------------------------------------------------------------- */
  .bloco2{display:grid;grid-template-columns:1fr 1px 184px;gap:0 14px;align-items:stretch}
  .col-acao{display:flex;flex-direction:column;gap:6px}
  /* Botão do mesmo grupo com a MESMA largura, e o grupo preenchendo a coluna:
     antes eram três larguras (138,2 / 141,3 / 80,7) numa fileira que deixava
     157,8px de sobra. */
  .col-acao .btn{width:100%;justify-content:center;padding:0 8px}

  /* a linha de estado: glifo E cor mudam juntos — quem não distingue verde de
     laranja continua lendo o estado pelo símbolo. Antes "ok" e "aviso" usavam o MESMO ●. */
  .est{display:flex;align-items:center;gap:8px;height:30px;font-size:11.5px;color:var(--texto-mudo)}

  /* A LINHA HORIZONTAL QUE SEPARA UM CAMPO DO OUTRO — pedido dela, 30/08:
     *"as linhas divisórias em todas as páginas (…) a primeira coluna serve como
     nome da linha e a divisória entre eles tem que estar clara. pra todas as
     abas"*. Mesmo molde da Iluminação (`aba04.py`), com a razão escrita lá.
     A ÚLTIMA não leva: separador depois do último campo vira moldura, e a
     moldura do quadro já existe. */
  .est{border-bottom:1px solid var(--rot-linha)}
  .col-est .est:last-child, .bat .est:last-child{border-bottom:0}
  /* custo de layout ZERO: `box-sizing:border-box` põe a borda dentro dos 30px. */

  .est .rot{flex:0 0 170px;white-space:nowrap;color:var(--rot-campo);font-weight:600}
  .est .val{color:var(--fg);font-weight:600;white-space:nowrap}
  .est .g{flex:0 0 14px;text-align:center;font-size:11px;font-weight:700}
  .est.ok .g{color:var(--green)} .est.ok .val{color:var(--green)}
  .est.warn .g{color:var(--orange)} .est.warn .val{color:var(--orange)}
  .est.info .g{color:var(--cyan)}
  /* `vm` = valor-mono. NÃO se chama `mono`: o esqueleto da Jogar já tem
     `.mono{font-family:'JetBrains Mono'}` (topo.html:30), que pegaria a LINHA
     inteira e levaria o RÓTULO junto — duas tipografias na mesma coluna de
     rótulos. É a mesma cicatriz de colisão de nome que obrigou `.nota` a virar
     `.nt` aqui dentro. Só o valor é mono. */
  .est.vm .val{font-family:'JetBrains Mono',monospace;font-weight:400;font-size:11px}
  /* O interruptor obedece à MESMA coluna de valores das outras linhas de estado:
     sem isto o `margin-left:auto` da `.chave` o jogava 85px à direita do início
     da coluna, colado no risco de 1px — a única exceção da aba. */
  .est .chave{margin-left:0}

  /* ---------------------------------------------------------------------
     O PERFIL DE BATERIA — o bloco que tomou o lugar do Gamepad virtual.
     Decisão dela, 28/08 (D-O-GAMEPAD-VIRTUAL-SAI-DA-INTERFACE): *"colocar Teto
     da Vibração (que na verdade é Perfil de Bateria) e colocar em sistema no
     lugar do Gamepad virtual"*.

     UMA COLUNA SÓ, e não as duas do irmão: aqui não há coluna de AÇÃO — a
     escolha é o próprio seletor, e uma barra de 1px separando o nada do nada
     desenharia uma divisão que não existe. A LARGURA continua igual (o `.par2`
     dá 1fr a cada metade) e a ALTURA também (o `align-items:stretch` do `.par2`
     faz esta metade herdar a altura do irmão) — que é o que ela pediu em 27/08:
     *"Altura e largura dos blocos O Hefesto e Gamepad virtual são iguais"*.
     --------------------------------------------------------------------- */
  .bat{display:flex;flex-direction:column}
  /* a linha do seletor é mais alta que uma linha de estado porque o `select`
     mede `--h-escolha` (36px) — encaixá-lo numa linha de 30 o cortaria. */
  .est.escolhe{height:var(--h-escolha)}
  /* A ROUPA DO `<select>` é de cada aba, não do esqueleto: o `topo.html` só lhe
     dá a ALTURA (`--h-escolha`, 36px, para não haver quatro alturas de campo na
     mesma janela). Estas seis linhas são as MESMAS do `aba08.py:477` — o
     dropdown que se mudou para cá não podia mudar de roupa no caminho. Sem
     elas ele volta a ser o `<select>` cru do Chrome: fundo claro e do tamanho
     que o sistema quiser, que foi o que a primeira foto desta rodada mostrou.
     (O dono único desta roupa é o `<style>` do esqueleto, e é para lá que ela
     vai quando o `monta.py` deixar de ser território de outro agente.) */
  select.pronto{border-radius:6px;font-size:11.5px;font-family:inherit;padding:0 8px;
    border:1px solid var(--border-forte);background:var(--app-bg);color:var(--texto-suave);
    cursor:pointer}
  select.pronto:hover{border-color:var(--comment)}
  /* O seletor começa na MESMA coluna dos valores das outras linhas e acaba na
     borda do bloco — como os quatro botões do irmão, que também vão de ponta a
     ponta da coluna deles. É a régua dela de 27/08: colunas terminando juntas. */
  .est select.pronto{flex:1;min-width:0}
  /* A `.frase` SAIU do CSS junto com o parágrafo que ela vestia (31/08/2026).
     O que ela dizia — onde o teto age e onde ainda não age — continua na tela,
     como duas linhas de estado: é a razão do `alcance_de_hoje()` no produto
     (*"silêncio, nesta tela, seria lido como «o teto vale para tudo»"*) dita em
     dado, não em prosa. Regra deixada para quem vier: um bloco desta aba ACABA
     onde o irmão acaba, e a cura do vão é conteúdo em altura — nunca
     `space-between`, nunca linha esticada. */

  /* a saúde: selo curto + veredito; o "o que eu vi / por que importa / o que fazer"
     mora na dica (D-TUDO-QUE-EXPLICA-VIRA-DICA). O selo carrega GLIFO e cor.
     25,5px e não 28,5: quatro linhas de achado passam a medir os mesmos 102px
     dos três botões ao lado, e as duas colunas acabam no mesmo y. */
  .saude{display:flex;align-items:center;gap:9px;height:25.5px;font-size:12px;color:var(--texto-suave);
         border-bottom:1px solid var(--border-sutil)}
  .saude:last-child{border-bottom:none}
  .saude .selo{flex:0 0 68px;text-align:center}
  .selo .sg{margin-right:4px;font-weight:700}
  .selo.ok{background:var(--green);color:var(--app-bg)}
  .selo.aviso{background:var(--orange);color:var(--app-bg)}
  .selo.nt{background:var(--comment);color:var(--app-bg)}
  .saude .txt{flex:1;display:flex;align-items:center;gap:7px;min-width:0}
  .saude .txt span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  /* ---------------------------------------------------------------------
     O EXAME EM DUAS COLUNAS, e a barra de 1px entre elas.
     Por que duas: com os três consertos rodando SOZINHOS no exame (decisão
     dela, 27/08), a coluna de botões caiu de sete para três — 102px — e o
     cartão de saúde continuou com oito achados. Uma coluna só deixava 126px de
     vão escuro ao lado dos botões, e a cura de um vão é na ALTURA: o cartão
     encolhe reflowando, não perdendo achado.
     --------------------------------------------------------------------- */
  .saude-cols{display:grid;grid-template-columns:1fr 1px 1fr;gap:0 18px}
  .col-lista{display:flex;flex-direction:column}
  /* Os três botões do exame não levam vão entre si: quatro linhas de achado
     medem 102px, e 3 × 34 dá exatamente 102. As duas colunas acabam juntas. */
  .exame .col-acao{gap:0}

  /* a fileira que não cabia vira LISTA: cinco botões somavam 1230px numa janela de 1180 */
  .lista{display:flex;flex-direction:column;gap:4px}
  .lista .btn{width:100%;justify-content:flex-start;padding:0 13px}
  .chave{margin-left:auto;width:36px;height:20px;border-radius:10px;background:var(--border-forte);
         position:relative;cursor:pointer;flex:0 0 36px}
  .chave::after{content:'';position:absolute;top:2px;left:2px;width:16px;height:16px;
                border-radius:50%;background:var(--texto-mudo)}
  .chave.on{background:var(--purple)}
  .chave.on::after{left:18px;background:var(--fg)}

  /* O painel tem a altura da coluna de botões ao lado (3 × 34 + 2 × 4 = 110):
     duas colunas irmãs acabam no mesmo y, e as quatro linhas cabem inteiras.
     A quinta linha aparecia cortada ao meio, que lê como quadro quebrado; o que
     ela dizia foi para o fim da segunda: a cor de fábrica só é perguntada NO
     CABO (`app/actions/config/secao_controles.py:929`), e por isso p2 e p3, que
     estão no rádio, não têm leitura. */
  .col-log{display:flex;flex-direction:column}
  .log{padding:10px 12px;border:1px solid var(--border-sutil);border-radius:7px;
       background:var(--app-bg);font-family:'JetBrains Mono',monospace;font-size:10.5px;
       line-height:1.6;color:var(--texto-mudo);height:110px;overflow:auto;white-space:pre}
""" + CSS_GLIFO


def est(rot, val, cls="", g="●", mono=False, dica="", ident=""):
    """Uma linha de estado: glifo, rótulo à esquerda, VALOR à direita.

    O `ident` vira `data-id` NA LINHA, não no `.val`: a pintura precisa de três
    coisas na mesma linha — o texto do valor, o glifo e a classe do selo — e um
    endereço só que as alcance é o que evita três endereços por linha. **`data-`
    e não `id`:** `id` é espaço global e esta página tem o SVG do logotipo
    dentro dela, com ids que o `monta.py` prefixa.

    A REGRA DA MAIÚSCULA DESTA CASA, escrita aqui em 28/08/2026 para as outras
    abas seguirem a mesma — antes cada aba escolhia sozinha, e a mesma coluna
    tinha "ligado" ao lado de "Wayland · COSMIC":

    * **Valor de campo começa com maiúscula.** É o que fica à direita de um
      rótulo, numa linha de estado ou num campo: `Ligado`, `Sim, e volta
      pausado`, `Os 4 controles`. Ele é uma RESPOSTA, não a continuação da frase
      do rótulo — "O Hefesto está" e "Ligado" são duas caixas, e quem lê a
      coluna de valores sozinha lê uma lista de respostas.
    * **O que não é valor de campo fica em minúscula:** a contagem no rótulo de
      uma seção (`8 linhas · nenhum aviso`), a legenda sob um elemento, o rótulo
      de uma coluna. Nenhum deles responde a um rótulo — são a moldura, não o
      conteúdo.
    * **Nome próprio, caminho e sigla mantêm a forma de fábrica:**
      `/dev/uinput`, `Wayland · COSMIC`, `054C:0CE6`. Capitalizar um caminho o
      quebraria; capitalizar uma sigla mudaria o que ela é.
    """
    t = f' title="{dica}"' if dica else ""
    i = f' data-id="{ident}"' if ident else ""
    return (f'''            <div class="est {cls}{' vm' if mono else ''}"{t}{i}>'''
            f'''<span class="g">{g}</span><span class="rot">{rot}</span>'''
            f'''<span class="val">{val}</span></div>''')


def saude(selo, g, txt, dica, glifos=()):
    # "nota" colidiria com a classe da LEGENDA da página (e o olhar.py esconde .nota)
    c = {"OK": "ok", "AVISO": "aviso", "NOTA": "nt"}[selo]
    gl = ""
    if glifos:
        gl = ('<span class="gls">'
              + "".join(glifo(n, tam=15) for n in glifos) + "</span>")
    return f'''            <div class="saude">
              <span class="selo {c}"><span class="sg">{g}</span>{selo}</span>
              <span class="txt">{gl}<span>{txt}</span></span>
              <span class="ajuda">?<span class="dica" style="left:auto;right:22px">{dica}</span></span>
            </div>'''


def item(rotulo, diz, cls="btn", gesto=""):
    """O que antes era texto ao lado do botão vira TOOLTIP dele. Pedido dela em
    27/08: 'todos os valores ao lado dos botões são valores que aparecem se
    deixarmos o mouse sobre o botão'.

    O `gesto` é o NOME DO QUE O BOTÃO FAZ, não do que ele parece: `desligar`, e
    não `btn-vermelho`. É por ele que o clique chega ao Python.
    """
    g = f' data-gesto="{gesto}"' if gesto else ""
    return f'''            <button class="{cls}" title="{diz}"{g}>{rotulo}</button>'''


def sel(opcoes, escolhida, dica="", ident="", gesto=""):
    """Um `<select>` com a opção escolhida marcada — a forma da casa.

    A MESMA do `aba08.py`: o dropdown que se mudou para cá não muda de roupa no
    caminho, senão a tela ganharia duas formas para a mesma escolha.
    """
    corpo = "".join(f'<option{" selected" if o == escolhida else ""}>{o}</option>'
                    for o in opcoes)
    i = f' data-id="{ident}"' if ident else ""
    g = f' data-gesto="{gesto}"' if gesto else ""
    return f'<select class="pronto" title="{dica}"{i}{g}>{corpo}</select>'


# --- o exame de hoje --------------------------------------------------------
# Os três consertos que sobraram RODAM SOZINHOS no exame (decisão dela, 27/08),
# e por isso os achados que eles curam aparecem no PRETÉRITO: "estava ligado em
# 2 jogos, desliguei". A palavra dela está no índice da onda.
ACHADOS = [
    saude("OK", "✓", "Regra de permissão dos controles instalada",
          "<b>O que eu vi:</b> a regra <b>70-hefesto.rules</b> está em /etc/udev/rules.d e foi lida pelo sistema."
          "<br><br><b>Por que importa:</b> sem ela o Hefesto não consegue escrever nos controles, e gatilho, luz e "
          "vibração ficam mudos nos quatro."
          "<br><br><b>O que fazer:</b> nada — está no lugar."),
    saude("OK", "✓", "O serviço sobe sozinho no login",
          "<b>O que eu vi:</b> a unidade <b>hefesto.service</b> está habilitada para o seu usuário."
          "<br><br><b>Por que importa:</b> sem isso você teria de ligar o Hefesto à mão toda vez que ligasse o computador."
          "<br><br><b>O que fazer:</b> nada. Para desfazer, é o interruptor <b>Ligar junto com o computador</b>, acima."),
    saude("OK", "✓", "Steam Input estava ligado em 2 jogos — desliguei",
          "<b>O que eu vi:</b> <b>Mortal Kombat 1</b> e <b>Elden Ring</b> estavam com o Steam Input ligado. O exame "
          "desligou nos dois, sem senha e sem fechar a Steam."
          "<br><br><b>Por que importa:</b> a Steam faz um espelho Xbox de <b>cada</b> controle que enxerga, inclusive "
          f"dos gamepads virtuais do Hefesto. Com {N} controles na mesa isso são {N} espelhos, e o jogo passaria a ver "
          f"<b>{2 * N}</b> onde você tem {N}. Alguns jogos escolhem o errado."
          "<br><br><b>O que fazer:</b> nada. Para refazer, é <b>Refazer os consertos automáticos</b>, ao lado."),
    saude("OK", "✓", f"Áudio dos {N} controles roteado",
          f"<b>O que eu vi:</b> o PipeWire está enxergando os {N} DualSense como saída e entrada."
          "<br><br><b>Por que importa:</b> é o que faz o alto-falante e o microfone de cada controle funcionarem."
          "<br><br><b>O que fazer:</b> nada. O volume de cada um fica na aba <b>Controles</b>.",
          glifos=("alto-falante", "mic")),
    saude("OK", "✓", "Nenhuma sobreposição picotando o jogo",
          "<b>O que eu vi:</b> o exame procurou camadas de gravação e de estatística sobre os jogos e não achou nenhuma."
          "<br><br><b>Por que importa:</b> sobreposição mal comportada engasga o jogo e a culpa costuma cair no controle."
          "<br><br><b>O que fazer:</b> nada agora. Para procurar de novo, é <b>Procurar sobreposição de novo</b>, ao lado — "
          "se achar, ele mostra qual é antes de tirar."),
    saude("NOTA", "i", "Um gamepad virtual por jogador (co-op)",
          f"<b>O que eu vi:</b> o co-op está ligado e o Hefesto criou <b>{N}</b> gamepads virtuais, um para cada controle."
          "<br><br><b>Por que importa:</b> é o que dá um jogador a cada pessoa em vez de todo mundo mexer no mesmo "
          f"boneco. É também por isso que <code>/dev/input/js*</code> tem {NOS} nós para {2 * N} aparelhos."
          "<br><br><b>O que fazer:</b> nada — é assim que o jogo local funciona.",
          glifos=("led-jogador",)),
    saude("NOTA", "i", "Proton fixado em 9.0-4 para 3 jogos",
          "<b>O que eu vi:</b> três jogos estão travados na versão de Proton que você validou."
          "<br><br><b>Por que importa:</b> uma atualização da Steam não vai trocar a versão sob os seus pés."
          "<br><br><b>O que fazer:</b> nada — é uma escolha sua, registrada. Para soltar ou trocar, é "
          "<b>Refazer a fixação do Proton</b>."),
    saude("NOTA", "i", f"Bluetooth: 1 adaptador, {len(BT)} controles no rádio",
          "<b>O que eu vi:</b> um adaptador ativo, com "
          + _lista(["o Player %d" % c["jogador"] for c in BT]) + " conectados por rádio."
          "<br><br><b>Por que importa:</b> o rádio é onde nascem os engasgos de entrada que parecem defeito do controle, "
          "e dois controles dividem a banda do mesmo adaptador."
          "<br><br><b>O que fazer:</b> nada aqui. Vizinhança, porta e orçamento de banda ficam na aba <b>Conexões</b>."),
]

MEIO = len(ACHADOS) // 2 + len(ACHADOS) % 2

D_HEFESTO = ('<span class="ajuda">?<span class="dica">'
             f'O Hefesto é um serviço que fica rodando em segundo plano. Ele é quem fala com os '
             f'controles — sem ele, o Linux vê {N} gamepads comuns e nada mais.<br><br>'
             f'<b>Reiniciar</b> resolve a maioria dos travamentos e não perde nenhum ajuste seu, '
             f'em nenhum dos {N}.<br><br>'
             '<b>Retomar</b> só acende quando o Hefesto está pausado. A pausa fica gravada em '
             'disco e <b>sobrevive a desligar o computador</b>: sem este botão, ele renasce pausado.'
             '</span></span>')

# O QUE CADA PERFIL FAZ, DERIVADO. Nenhum rótulo e nenhum número digitados: os
# três nomes vêm de `ROTULOS_DOS_PERFIS`, o teto de `TETO_POR_PERFIL` +
# `RUMBLE_POLICY_MULT`, e a lista do que ele ainda não alcança de
# `LINHAS_DO_TETO`. No dia em que a barra de luz ganhar ponto de aplicação, ela
# sai da frase sozinha — nas duas telas, porque as duas leem o mesmo dono.
_LINHAS_DA_DICA = "".join(
    f'<b>{ROT_PERFIL[p]}</b> — '
    + (f'põe teto na vibração: {forca_do_perfil(p)}.' if forca_do_perfil(p)
       else ('você decide item a item, aba por aba.' if p == ORC["PERFIS"][-1]
             else 'nada é limitado; o que o jogo pedir chega inteiro.'))
    + '<br>'
    for p in ORC["PERFIS"])

D_BATERIA = ('<span class="ajuda">?<span class="dica">'
             'O que fica ligado na mesa inteira, e quanto isso custa de bateria. As abas '
             'continuam mandando no que fazem — nenhum ajuste seu é apagado.<br><br>'
             + _LINHAS_DA_DICA +
             '<br>É o perfil da <b>mesa</b>: vale para os '
             f'{N} controles. Cada um pode sobrepô-lo na linha dele.'
             '</span></span>')

D_EXAME = ('<span class="ajuda">?<span class="dica">'
           'Um exame do que costuma brigar com os controles nesta máquina. Cada linha diz '
           '<b>o que está</b>; o <b>?</b> ao lado dela diz o que foi visto, por que importa e o '
           'que fazer.<br><br>'
           'O selo carrega <b>símbolo e cor</b> juntos, para quem não distingue verde de '
           'laranja ler o estado pelo desenho.<br><br>'
           'Os três botões à direita <b>já rodaram sozinhos neste exame</b> — é por isso que os '
           'achados falam no passado ("estava ligado em 2 jogos, desliguei"). O botão serve para '
           '<b>refazer</b>, quando você mexeu em alguma coisa e quer conferir de novo.'
           '</span></span>')

D_AVANCADO = ('<span class="ajuda">?<span class="dica">'
              'Gestos raros. <b>Restaurar de fábrica</b> devolve o perfil de fábrica e pergunta '
              'antes — os seus perfis salvos continuam onde estão.<br><br>'
              'O painel ao lado é a saída crua do Hefesto: é daqui que você copia quando for '
              'relatar um problema.'
              '</span></span>')

MIOLO = f'''
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">Sistema</span>
        <span class="ajuda">?<span class="dica">
          Esta aba é sobre a <b>máquina</b>, não sobre um controle: o serviço que fala com os
          {N}, os gamepads virtuais que ele cria para os jogos, o exame do que costuma brigar
          com controle nesta máquina, e os gestos raros.<br><br>
          Por isso a fita lá em cima está apagada — nada aqui muda de controle para controle.
        </span></span>
      </div>
      <div class="quadro-corpo">

        <!-- ---------- O HEFESTO · PERFIL DE BATERIA ---------- -->
        <div class="sec-rot sr-par2">
          <span>O Hefesto {D_HEFESTO}</span><span></span>
          <span>Perfil de Bateria {D_BATERIA}</span>
        </div>
        <div class="par2">

          <div class="bloco2">
            <div class="col-est">
{est("O Hefesto está", "Ligado", "ok", "✓", ident=_id("hefesto-estado"))}
{est("Pausado", "Sim, e volta pausado", "warn", "!", dica="A pausa fica gravada em disco e sobrevive a desligar o computador. O botão Retomar, ao lado, é a saída — até 27/08/2026 só o terminal saía dela.", ident=_id("hefesto-pausa"))}
{est("Trocar de perfil ao abrir o jogo", "Ligado", "ok", "✓", ident=_id("hefesto-troca-de-perfil"))}
{est("Como ele enxerga a janela", "Wayland · COSMIC", "info", "◆", ident=_id("hefesto-ambiente"))}
              <div class="est" data-id="{_id("hefesto-autostart")}"><span class="g"></span><span class="rot">Ligar junto com o computador</span>
                <span class="chave on" data-gesto="{_gesto("autostart")}"></span></div>
            </div>
            <div class="risco"></div>
            <div class="col-acao">
{item("Retomar", "Tira o Hefesto da pausa agora. Só acende com a pausa ativa — e ela sobrevive a desligar o computador.", "btn verde", gesto=_gesto("retomar"))}
{item("Reiniciar o Hefesto", "Desliga e liga. Resolve a maioria dos travamentos e não perde nenhum ajuste seu.", gesto=_gesto("reiniciar"))}
{item("Atualizar", "Relê tudo o que esta aba mostra. Não muda nada.", gesto=_gesto("atualizar"))}
{item("Desligar o Hefesto", f"Os {N} viram gamepads comuns do Linux. Pergunta antes, dizendo o que se perde.", "btn vermelho", gesto=_gesto("desligar"))}
            </div>
          </div>

          <div class="risco"></div>

          <div class="bat">
            <div class="est escolhe"><span class="g"></span>
              <span class="rot">O perfil da mesa</span>
              {sel([ROT_PERFIL[p] for p in ORC["PERFIS"]], ROT_PERFIL[PERFIL_DA_MESA],
                   dica=f"O que fica ligado na mesa inteira, e quanto isso custa de bateria. Vale para os {N} controles — cada um pode sobrepô-lo na linha dele.",
                   ident=_id("bateria-perfil"), gesto=_gesto("perfil-da-mesa"))}
            </div>
{est("O que ele impõe", impoe(PERFIL_DA_MESA), "info", "◆", dica="O que este perfil limita hoje, na mesa inteira. O degrau vem de RUMBLE_POLICY_MULT, no daemon — nenhum número escrito nesta tela.", ident=_id("bateria-impoe"))}
{est("Vale para", f"Os {N} controles", "info", "◆", dica="É o teto da MESA. Cada controle pode sobrepô-lo na linha dele, e o campo de lá diz qual dos dois está valendo.", ident=_id("bateria-vale-para"))}
{est("O teto alcança", _frase(ALCANCA), "info", "◆", dica="Onde o teto do perfil age de verdade hoje. Sai de LINHAS_DO_TETO, no produto — nenhum nome escrito nesta tela.")}
{est("Ainda sem teto", _frase(PENDENTES), "info", "◆", dica="O perfil ainda não tem por onde limitar estes. Cada um entra quando ganhar ponto de aplicação no daemon, e some daqui sozinho.")}
            <!-- O VÃO DE 58px, E POR QUE ELE ERA O DEFEITO — 31/08/2026.
                 Palavra dela: *"aqui em perfil da bateria essa seção tá muito feia
                 e distoante do resto da página, tá destacando negativamente"*.

                 MEDIDO no Chrome antes de mexer: o bloco tem 154px (a altura vem
                 do irmão, "O Hefesto", que soma 4 botões de 34 + 3 vãos de 6), e o
                 conteúdo daqui tinha 96 — 36 do seletor + 30 + 30. Sobravam **58px
                 de painel vazio**, o único vão da aba: as outras cinco colunas
                 desta página são engenhadas para ACABAR NO MESMO y (4 achados de
                 25,5 = 3 botões de 34 = 102; 3 botões de 34 + 2 vãos = o log de
                 110). Esta era a única que não acabava com a irmã, e por isso era
                 a única que destoava.

                 O vão nasceu em 30/08, quando a `.frase` que o preenchia saiu por
                 repetir a dica. Tirar o texto estava certo; deixar o buraco, não —
                 e o buraco é o que ela viu no dia seguinte.

                 A CURA NÃO É DEVOLVER A PROSA. O que a frase dizia vira DADO, na
                 mesma gramática do resto da página (rótulo → valor): duas linhas
                 de estado de 30px. 36 + 30×4 = 156, e o irmão estica 2px junto.
                 Medido depois: vão 0, e o miolo ainda não rola (sobram 2px).
                 E a dica perdeu o parágrafo que estas duas linhas passaram a
                 dizer — na conta final a tela tem MENOS texto que em 29/08, não
                 mais. -->
          </div>

        </div>

        <!-- ---------- SAÚDE DO SISTEMA + PREPARAR OS JOGOS ---------- -->
        <div class="sec-rot sr-exame sec-alta">
          <span>O exame de hoje {D_EXAME}
            <span class="conta" data-id="{_id("exame-contagem")}">{len(ACHADOS)} linhas <span class="sep">·</span> nenhum aviso</span></span>
          <span></span>
          <span>Preparar os jogos</span>
        </div>
        <div class="exame">
          <div class="saude-cols" data-id="{_id("exame-lista")}">
            <div class="col-lista">
{chr(10).join(ACHADOS[:MEIO])}
            </div>
            <div class="risco"></div>
            <div class="col-lista">
{chr(10).join(ACHADOS[MEIO:])}
            </div>
          </div>
          <div class="risco"></div>
          <div class="col-acao">
{item("Refazer os consertos automáticos", f"Sem senha e sem fechar nada: arruma o áudio dos {N} controles, desliga o Steam Input onde ele atrapalha e põe a linha de inicialização nos jogos instalados, com cópia de segurança. O exame já rodou isto — o botão refaz.", "btn verde", gesto=_gesto("refazer-consertos"))}
{item("Refazer a fixação do Proton", "Trava de novo o Proton que você validou nos jogos escolhidos — e diz o motivo em português quando não dá.", gesto=_gesto("refazer-proton"))}
{item("Procurar sobreposição de novo", "Procura de novo a camada que picota o jogo. Se achar, mostra qual é antes de tirar.", gesto=_gesto("procurar-camadas"))}
          </div>
        </div>

        <!-- ---------- AVANÇADO + DETALHES ---------- -->
        <div class="sec-rot sr-avancado sec-alta">
          <span>Avançado {D_AVANCADO}</span><span></span>
          <span>Detalhes técnicos</span>
        </div>
        <div class="avancado">
          <div class="lista">
{item("Restaurar de fábrica", "Devolve o perfil de fábrica. Pergunta antes, e os seus perfis salvos continuam onde estão.", "btn vermelho", gesto=_gesto("restaurar-de-fabrica"))}
{item("Ver os plugins carregados", "Lista os plugins do daemon e relê. Hoje só o terminal alcança isso.", gesto=_gesto("ver-plugins"))}
{item("Ver detalhes", "Joga as últimas 80 linhas do registro técnico no painel ao lado.", gesto=_gesto("ver-detalhes"))}
          </div>
          <div class="risco"></div>
          <div class="col-log">
            <div class="log" data-id="{_id("registro-texto")}">[23:41:02] daemon pronto · {N} controles · {N} gamepads virtuais · uinput ok
[23:41:02] {" · ".join(f'p{c["jogador"]} {c["via"].lower()}' for c in MESA)} · fw 0x0356 nos {N} · cor de fábrica só no cabo ({", ".join(f'p{c["jogador"]}' for c in USB)})
[23:41:07] exame: steam input desligado em 2 jogos · proton 9.0-4 fixado em 3
[23:41:09] perfil "Mortal Kombat" aplicado aos {N} · gatilho L2 escrito, sem leitura de volta</div>
          </div>
        </div>

      </div>
    </div>
'''

# O que a legenda conta sobre o perfil também é DERIVADO: uma legenda que
# digitasse "Bateria longa" ou "30%" seria o mesmo literal que a tela deixou de
# ter, dois parágrafos abaixo dele.
rotulos = _lista([f'<b>{ROT_PERFIL[p]}</b>' for p in ORC["PERFIS"]])
forca = forca_do_perfil(_SO_ESTE)
rot_mesa = ROT_PERFIL[PERFIL_DA_MESA]
impoe_texto = impoe(PERFIL_DA_MESA)
n_achados = len(ACHADOS)

LEGENDA = f'''<div class="nota">
  <h2>O defeito que esta rodada curou: 93px escondidos</h2>
  <ul>
    <li><b>O que a foto mostrava.</b> O miolo rolava <b>93px por dentro</b>: o segundo botão do
      "Avançado" saía <b>fatiado ao meio</b> e o painel de registro mostrava <b>uma</b> das quatro
      linhas. Nada na tela dizia que havia mais.</li>
    <li><b>A conta que explica.</b> O miolo tem {MIOLO_H}px, dos quais 508 de conteúdo. Cada quadro
      custa <b>54px só de moldura</b> (28 do topo, 24 do padding do corpo, 2 de borda), mais 14px
      de vão entre fileiras. <b>Quatro quadros em três fileiras = 190px de moldura</b> para 411px
      de conteúdo: 411 + 190 + 34 = <b>635</b>, numa janela de {MIOLO_H}.</li>
    <li><b>Espremer não fechava a conta.</b> Com toda linha no mínimo — botão colado em botão,
      rótulo sem respiro — as três fileiras ainda somavam ~550. O que sobrava era a
      <b>moldura repetida</b>, e foi ela que saiu.</li>
    <li><b>Um quadro só, e é a norma da casa.</b> Das dez abas, <b>sete têm um quadro só</b>, com o
      nome da aba no título e as seções por dentro (<code>sec-rot</code>, como a Navegação e a
      Vibração). As duas que fugiam disso eram exatamente as duas que escondiam conteúdo: esta e a
      Conexões. As seções viraram <b>faixas rotuladas</b> dentro de um quadro:
      <b>54px de moldura no lugar de 190</b>. Hoje o conteúdo mede <b>{ALTURA}px</b> em
      {MIOLO_H} — <b>nada rola, nada é fatiado</b>.</li>
    <li><b>Nenhuma linha foi cortada por falta de espaço.</b> Os 10 botões, os {n_achados} achados e as
      4 linhas do registro continuam todos na tela — o que saiu depois saiu por decisão dela, não
      por caber. O painel de registro <b>ganhou</b> altura (89 → 110px), para acabar no mesmo y da
      coluna de botões ao lado.</li>
  </ul>

  <h2>O Gamepad virtual saiu, e o Perfil de Bateria tomou o bloco</h2>
  <ul>
    <li><b>A palavra dela, 28/08</b> (<code>D-O-GAMEPAD-VIRTUAL-SAI-DA-INTERFACE</code>):
      <i>"some da interface; o controle já tá certinho hoje. aquilo foi pra outro momento que não
      faz sentido na interface hoje."</i> Saiu o bloco inteiro — as cinco linhas de estado
      (<i>Gamepad virtual (uinput)</i>, <i>Nó do gamepad virtual</i>, <i>Aparelhos físicos</i>,
      <i>Código do fabricante</i>, <i>Controles detectados</i>), os quatro chips
      <code>P1</code>..<code>P4</code> e o diagraminha da cadeia.</li>
    <li><b>E no lugar dele, o que ela mandou:</b> <i>"colocar Teto da Vibração (que na verdade é
      Perfil de Bateria) e colocar em sistema no lugar do Gamepad virtual."</i> O dropdown vinha da
      <b>Conexões</b>, da seção que se chamava <i>Desempenho</i> — e o nome dela é que estava
      errado: o produto já chama a chave de <code>PERFIL_BATERIA_LONGA</code>
      (<code>secao_orcamento.py:127</code>), e a <code>D-PERFIL-DE-DESEMPENHO</code> registra que o
      perfil <i>"decide o que custa BATERIA"</i>.</li>
    <li><b>O bloco herdou a medida do irmão, e está medido:</b> <b>535,5 × 156px</b>, o mesmo
      <i>x</i>, <i>y</i>, largura e altura do bloco "O Hefesto" — que é o que ela pediu em 27/08
      (<i>"Altura e largura dos blocos O Hefesto e Gamepad virtual são iguais"</i>). O miolo
      continua em <b>{MIOLO_H}px sem rolar nada</b>.</li>
    <li><b>Nenhum rótulo e nenhum número foram digitados.</b> Os três perfis
      ({rotulos}), a tradução perfil→disco e o degrau do teto são <b>lidos do
      produto por AST</b> — <code>ROTULOS_DOS_PERFIS</code>, <code>TETO_POR_PERFIL</code>,
      <code>RUMBLE_POLICY_MULT</code> e <code>LINHAS_DO_TETO</code>. É a mesma cura que a Conexões
      já tinha: em 28/08 a dica de lá afirmava que "Bateria longa" corta a força em <b>60%</b>, e o
      produto corta em <b>{forca}</b> — o dobro do limite real, e nenhuma régua podia vê-lo, porque
      era literal.</li>
    <li><b>A leitura "Sem teto" NÃO veio junto</b> (<code>D-O-SEM-TETO-SAI-DOS-DOIS-LUGARES</code>):
      ela mandou tirá-la dos dois lugares da Conexões, e trazer o campo para cá seria fazê-lo
      renascer numa terceira tela. Veio o seletor. A tela não afirma teto onde não há — diz
      <i>"{impoe_texto}"</i> e <b>nomeia em duas linhas</b> onde o teto age e onde ainda não age,
      que é a razão escrita do <code>alcance_de_hoje()</code> no produto: <i>"silêncio, nesta
      tela, seria lido como «o teto vale para tudo»"</i>.</li>
    <li><b>Duas minúsculas sumiram sozinhas:</b> <i>os seus</i> e <i>um por jogador</i> eram os
      rótulos da cadeia, e foram embora com ela.</li>
    <li><b>O vão de 58px, e a régua que nasceu dele — 31/08/2026.</b> Palavra dela: <i>"aqui em
      perfil da bateria essa seção tá muito feia e distoante do resto da página, tá destacando
      negativamente"</i>. O bloco tinha <b>96px de conteúdo em 154</b> — o único vão da aba, num
      lugar onde as outras duas faixas são engenhadas para acabar no mesmo <i>y</i>. Ele nasceu em
      30/08, quando a <code>.frase</code> saiu por repetir a dica: tirar o texto estava certo,
      deixar o buraco não. O que a frase dizia virou <b>duas linhas de estado</b> — a gramática do
      resto da página —, e a dica perdeu o parágrafo que elas passaram a dizer: <b>menos texto na
      tela que em 29/08, não mais</b>. Agora há portão no gerador: ele lê as quatro alturas do CSS
      e do esqueleto, conta as linhas dos dois blocos e <b>reprova em voz alta</b> quando eles
      deixam de acabar juntos — <code>96px … 58px de painel vazio</code>, com a cura arrancada.</li>
  </ul>

  <h2>A regra da maiúscula, escrita para as outras abas seguirem</h2>
  <ul>
    <li><b>Valor de campo começa com maiúscula:</b> <i>Ligado</i>, <i>Sim, e volta pausado</i>,
      <i>Nada é limitado</i>, <i>Os {N} controles</i>. Ele é uma <b>resposta</b> a um rótulo, não a
      continuação da frase dele — quem lê a coluna de valores sozinha lê uma lista de respostas.</li>
    <li><b>O que não é valor de campo fica em minúscula:</b> a contagem no rótulo de uma seção
      (<i>{n_achados} linhas · nenhum aviso</i>), a legenda sob um elemento, o rótulo de uma coluna.
      Nenhum deles responde a um rótulo — são a moldura, não o conteúdo. <b>É por isso que aquela
      contagem continua minúscula</b>, e não porque passou despercebida.</li>
    <li><b>Nome próprio, caminho e sigla mantêm a forma de fábrica:</b> <code>Wayland · COSMIC</code>.
      Capitalizar um caminho o quebraria; capitalizar uma sigla mudaria o que ela é.</li>
    <li>A regra mora no <code>est()</code> do gerador desta aba, para a próxima não ter de
      reinventá-la.</li>
  </ul>

  <h2>O que continua valendo desde ontem</h2>
  <ul>
    <li><b>Toda contagem sai da <code>MESA</code>.</b> "{len(BT)} controles no rádio", "áudio dos
      {N} controles", "vale para os {N} controles", as linhas do registro técnico e o cabeçalho —
      nenhum "quatro" digitado. Um controle a mais na bancada muda todos de uma vez.</li>
    <li><b>Sete botões de "Preparar os jogos" viraram três</b>, e os três <b>rodam sozinhos no
      exame</b> — por isso os achados falam no pretérito. O rótulo virou <b>Refazer</b>.</li>
        <li><b>Os glifos são os do mapa</b> (<code>assets/glyphs/</code>): alto-falante e microfone na
      linha do áudio, o indicador de jogador na linha do co-op.</li>
  </ul>

  <h2>O que eu assumi — e que precisa do olho dela</h2>
  <ul>
    <li><b>O título do quadro virou "Sistema"</b>, o nome da aba, como na Iluminação, na Vibração,
      na Navegação e nos Perfis. Os títulos antigos — <i>O Hefesto</i>, <i>Perfil de Bateria</i>,
      <i>Avançado</i> — viraram rótulos de faixa, e cada um levou o seu <b>?</b> junto. O do exame
      levou também a contagem de linhas.</li>
    <li><b>As linhas de achado encolheram de 28,5 para 25,5px.</b> Quatro delas passam a medir os
      mesmos 102px dos três botões ao lado, e as duas colunas acabam no mesmo y — que é a regra da
      casa. Se ficou apertado ao olho dela, o caminho é devolver 3px e tirá-los da faixa de cima.</li>
    <li><b>O painel de registro cresceu para 110px</b> para acabar no mesmo y dos três botões de
      "Avançado". As quatro linhas cabem inteiras, e sobra o respiro de um terminal.</li>
    <li><b>O perfil aparece com "{rot_mesa}" escolhido</b>, que é o estado que o dropdown já
      mostrava na Conexões. Trocá-lo no transplante faria as quatro linhas de teto por controle de
      lá passarem a mentir sobre o global — o estado é dela, não meu.</li>
    <li><b>Os {N} controles não aparecem mais nesta aba.</b> O rol com nome, bateria e transporte é
      da <b>Jogar</b> e da <b>Controles</b>; com a cadeia fora, nada aqui é por controle.</li>
  </ul>

  <h2>Ainda aberto — vai para o chat, com escolhas</h2>
  <ul>
    <li><b>O interruptor "avisar quando a bateria estiver acabando" mora aqui, na Sistema?</b> As
      duas funções de notificação estão escritas e testadas e ninguém as chama
      (<code>integrations/desktop_notifications.py:272</code>). Com {N} controles a pergunta pesa
      mais: são {N} baterias a acabar em horários diferentes. Opções: (a) na faixa <b>Perfil de
      Bateria</b>, que nasceu hoje e é onde a palavra "bateria" agora mora; (b) na faixa "O
      Hefesto"; (c) na aba Controles, junto da bateria de cada um.</li>
    <li><b>Entra uma linha de saúde para o canal DSX?</b> A porta 127.0.0.1:6969 aceita gatilho e
      cor de qualquer programa local e nenhuma tela conta isso
      (<code>daemon/udp_server.py</code>). É a explicação que falta quando o gatilho muda sozinho.
      Opções: (a) nono achado; (b) só no painel de Detalhes técnicos; (c) fica invisível.</li>
  </ul>

  <h2>Já decidido por ela — não é pergunta</h2>
  <ul>
    <li><b>Os botões de Steam ficam na Sistema</b> (D-A-ABA-LANCADORES-NASCE-PLACEHOLDER):
      <i>"a aba nova não existe ainda"</i>.</li>
    <li><b>O "o que fazer" das linhas de saúde fica na dica</b> (D-TUDO-QUE-EXPLICA-VIRA-DICA): na
      tela ficam título, rótulo e estado; explicação vai para o "?".</li>
    <li><b>A aba é mostrada com a pausa ATIVA</b> — sem isso o botão Retomar não teria o que
      ilustrar. No produto ele só acende nesse estado.</li>
    <li><b>O Gamepad virtual sai da interface</b> (<code>D-O-GAMEPAD-VIRTUAL-SAI-DA-INTERFACE</code>)
      e <b>o Perfil de Bateria toma o bloco</b> — as duas são a mesma decisão dela, de 28/08.</li>
    <li><b>A leitura "Sem teto" sai dos dois lugares</b>
      (<code>D-O-SEM-TETO-SAI-DOS-DOIS-LUGARES</code>): vem o seletor, e só.</li>
  </ul>
</div>

</body>
</html>
'''

# ---------------------------------------------------------------------------
# O PORTÃO DOS DOIS BLOCOS DA PRIMEIRA FAIXA — 31/08/2026.
#
# Ele existe porque o defeito que ela apontou hoje era INVISÍVEL para toda régua
# desta casa: o `regua.py` deu verde sobre um bloco com **58px de painel vazio**,
# e o mockup abriu assim por um dia. O que a página promete é que colunas irmãs
# ACABAM NO MESMO y — é a conta escrita nas outras duas faixas (4 achados de
# 25,5 = 3 botões de 34; 3 botões + 2 vãos = o log de 110) — e essa promessa não
# tinha quem a cobrasse na faixa de cima.
#
# NENHUM NÚMERO É DIGITADO AQUI: as quatro alturas são LIDAS — duas do CSS desta
# aba, duas dos tokens do esqueleto —, e as contagens de linha e de botão saem
# do HTML já montado. Digitá-las seria repetir o defeito que este arquivo inteiro
# evita: um segundo dono que diverge calado.
# ---------------------------------------------------------------------------
def _medida(texto, regra, prop):
    """`height:30px` de dentro de uma regra de CSS — lido, nunca digitado."""
    bloco = re.search(re.escape(regra) + r"\{([^}]*)\}", texto)
    if not bloco:
        raise SystemExit(f"ERRO: a regra CSS `{regra}` sumiu — o portão da faixa "
                         "de cima mede por ela.")
    px = re.search(prop + r":(\d+(?:\.\d+)?)px", bloco.group(1))
    if not px:
        raise SystemExit(f"ERRO: `{regra}` não declara mais `{prop}` em px.")
    return float(px.group(1))


def _token(texto, nome):
    """`--h-escolha:36px` do esqueleto. O `:root` dele aparece mais de uma vez,
    então a busca é pelo TOKEN, não pelo bloco que o hospeda."""
    px = re.search(re.escape(nome) + r":(\d+(?:\.\d+)?)px", texto)
    if not px:
        raise SystemExit(f"ERRO: o esqueleto não declara mais `{nome}` em px — "
                         "o portão da faixa de cima mede por ele.")
    return float(px.group(1))


def _conta(html, de, ate, o_que):
    """Quantas vezes `o_que` aparece entre dois marcos do HTML montado."""
    i = html.index(de)
    return html[i:html.index(ate, i)].count(o_que)


_TOPO = (pathlib.Path(__file__).parent / "topo.html").read_text()
H_EST = _medida(CSS, ".est", "height")                 # a linha de estado
GAP_ACAO = _medida(CSS, ".col-acao", "gap")            # o vão entre botões
H_ESCOLHE = _token(_TOPO, "--h-escolha")               # select, campo, escolha
H_ACAO = _token(_TOPO, "--h-acao")                     # botão de ação

_N_BAT = _conta(MIOLO, '<div class="bat">', "<!-- ---------- SAÚDE", 'class="est')
_N_EST = _conta(MIOLO, '<div class="col-est">', '<div class="risco">', 'class="est')
_N_BTN = _conta(MIOLO, '<div class="col-acao">', "</div>", "<button")

#: O seletor mede `--h-escolha`; as outras linhas do bloco medem uma linha de
#: estado. O irmão é o mais alto entre a coluna de estados e a de botões.
_ALT_BAT = H_ESCOLHE + (_N_BAT - 1) * H_EST
_ALT_IRMAO = max(_N_EST * H_EST, _N_BTN * H_ACAO + (_N_BTN - 1) * GAP_ACAO)
#: 2px de tolerância: é o que o seletor de 36 custa a mais que a linha de 30, e
#: é o desencontro que a faixa já carrega hoje sem parecer vão.
if abs(_ALT_BAT - _ALT_IRMAO) > 2:
    raise SystemExit(
        f"ERRO: o Perfil de Bateria mede {_ALT_BAT:.0f}px e o bloco 'O Hefesto' "
        f"mede {_ALT_IRMAO:.0f}px — {abs(_ALT_BAT - _ALT_IRMAO):.0f}px de painel "
        "vazio na primeira faixa. Foi exatamente isto que ela viu em 31/08/2026 "
        '("essa seção tá muito feia e distoante do resto da página"). Duas '
        "colunas irmãs desta aba acabam no mesmo y — dê conteúdo ao bloco curto "
        "ou tire altura do alto, mas não entregue o vão.")

n = monta("09-sistema", "Sistema", MIOLO, CSS, fita_viva=False, legenda=LEGENDA)
print(f"09-sistema: OK, {n} divs")
