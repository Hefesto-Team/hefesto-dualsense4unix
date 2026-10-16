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

# geradores 08 e 09 pararam de RODAR por isso, calados até alguém tentar:
import onde  # noqa: E402
from onde import RAIZ as R  # noqa: E402

from hefesto_dualsense4unix.interface import janela as _ponte  # noqa: E402

N = len(CONECTADOS)
LUGARES = len(MESA)
USB = [c for c in CONECTADOS if c["via"] == "USB"]
BT = [c for c in CONECTADOS if c["via"] == "BT"]
#: era `2 * N + N` (cada DualSense publica DOIS — o gamepad e os sensores de


MIOLO_H, ALTURA = _ponte.MIOLO_NO_PISO, 530


def _lista(nomes):
    """`a`, `b` e `c` — em português, com "e" antes do último."""
    return nomes[0] if len(nomes) == 1 else f"{', '.join(nomes[:-1])} e {nomes[-1]}"


def _frase(nomes, curto=True):
    """A mesma lista, em CAIXA DE FRASE: só a primeira letra é maiúscula."""
    curtos = [APELIDO_NA_TELA.get(n, n) for n in nomes] if curto else list(nomes)
    return _lista([curtos[0]] + [n[0].lower() + n[1:] for n in curtos[1:]])


def _valor(no, ja):
    """O valor de um nó de AST, resolvendo NOME contra o que já foi lido."""
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
    """As constantes de módulo daquele arquivo, lidas sem importar nada."""
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
            continue
        if alvo.id in nomes:
            achado[alvo.id] = ja[alvo.id]
    if faltam := set(nomes) - set(achado):
        raise SystemExit(f"ERRO: {caminho} não tem mais {sorted(faltam)} — "
                         f"a tela dependia deles.")
    return achado


ORC = _constantes(R / "src/hefesto_dualsense4unix/app/actions/config/secao_orcamento.py",
                  {"PERFIS", "ROTULOS_DOS_PERFIS", "TETO_POR_PERFIL", "LINHAS_DO_TETO"})

#: `src/hefesto_dualsense4unix/interface/sistema.py` — que é versionado, viaja em
_CONTRATO = _constantes(R / "src/hefesto_dualsense4unix/interface/sistema.py",
                        {"ENDERECOS", "GESTOS"})
ENDERECOS = _CONTRATO["ENDERECOS"]
GESTOS = _CONTRATO["GESTOS"]

_DO_PACOTE = _constantes(
    R / "src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py",
    {"APELIDO_NA_TELA", "CAMPO_DO_MODO_AVULSO", "CAMPO_DO_STATUS", "CAMPO_DO_VERDE",
     "CAMPO_DAS_CORRECOES", "TAMANHOS_DA_INTERFACE", "CAMPO_DO_TAMANHO"})
APELIDO_NA_TELA = _DO_PACOTE["APELIDO_NA_TELA"]
CAMPO_DO_MODO_AVULSO = _DO_PACOTE["CAMPO_DO_MODO_AVULSO"]
CAMPO_DO_STATUS = _DO_PACOTE["CAMPO_DO_STATUS"]
CAMPO_DO_VERDE = _DO_PACOTE["CAMPO_DO_VERDE"]
CAMPO_DAS_CORRECOES = _DO_PACOTE["CAMPO_DAS_CORRECOES"]
TAMANHOS_DA_INTERFACE = _DO_PACOTE["TAMANHOS_DA_INTERFACE"]
CAMPO_DO_TAMANHO = _DO_PACOTE["CAMPO_DO_TAMANHO"]


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


#: POR QUE NÃO UMA ENTRADA EM `aba_sistema.ENDERECOS`: aquele dicionário é o
#: a fonte do dado (`state_full["paused"]`, `storm_report:755`). A razão do
#: cinza não é um valor novo do produto: é a MESMA `aba_sistema.travas()` que a
#: `interface/sistema.py` está FORA da posse desta frente, e por isso a derivação
SUFIXO_DA_RAZAO = "-razao"


def _razao(nome):
    """O `data-campo` onde a razão do cinza daquele gesto é escrita."""
    return f"{_gesto(nome)}{SUFIXO_DA_RAZAO}"


#: AS DUAS LINHAS DO TETO («Com limite», «Sem limite») SAÍRAM EM 25/09/2026,
MULT = _constantes(R / "src/hefesto_dualsense4unix/daemon/subsystems/rumble.py",
                   {"RUMBLE_POLICY_MULT"})["RUMBLE_POLICY_MULT"]
COM_TETO = _constantes(R / "src/hefesto_dualsense4unix/core/rumble.py",
                       {"_ORCAMENTO_COM_TETO"})["_ORCAMENTO_COM_TETO"]

ROT_PERFIL = ORC["ROTULOS_DOS_PERFIS"]
PERFIL_DA_MESA = ORC["PERFIS"][0]
ALCANCA = [linha["nome"] for linha in ORC["LINHAS_DO_TETO"] if linha["tem_ponto"]]
PENDENTES = [linha["nome"] for linha in ORC["LINHAS_DO_TETO"] if not linha["tem_ponto"]]


def teto_do_perfil(perfil):
    """O teto que um perfil da TELA impõe, ou `None` quando não há teto."""
    chave = ORC["TETO_POR_PERFIL"][perfil]
    return None if chave != COM_TETO else MULT[COM_TETO]


def forca_do_perfil(perfil):
    """`"30% da força"`, ou `None` quando o perfil não põe teto nenhum."""
    teto = teto_do_perfil(perfil)
    return None if teto is None else f"{round(teto * 100)}% da força"


_COM_TETO = [p for p in ORC["PERFIS"] if teto_do_perfil(p) is not None]
if len(_COM_TETO) != 1:
    raise SystemExit("ERRO: a frase do perfil de bateria afirma que UM perfil põe teto, "
                     f"e agora são {len(_COM_TETO)}: {_COM_TETO}. Reescreva a frase.")
_SO_ESTE = _COM_TETO[0]


def impoe(perfil):
    """O que o perfil escolhido impõe — o valor curto da linha de estado."""
    forca = forca_do_perfil(perfil)
    return f"Vibração em {forca}" if forca else "Nada é limitado"


CSS = """
  /* ---------- Sistema, em três seções (A-09-SISTEMA-EM-TRES-SECOES-01, 25/09/2026) ----------
     Pedido: *«praticamente vamos só mudar de lugar as coisas dessa aba»*.
     1. Status (seis linhas, em três colunas);
     2. Configurações avançadas (quatro colunas de botões);
     3. os Detalhes técnicos, com a altura que sobra.
     O quadro é `estica`: a seção 3 é a única que sabe crescer, e cresce. */

  /* `minmax(0,1fr)` EM TODA FAIXA — a lição de 31/08 continua valendo: `1fr` tem
     por piso o CONTEÚDO, e uma frase longa do exame empurraria a coluna vizinha
     para fora do quadro. A régua 5, lá embaixo, cobra as duas. */
  .status3{display:grid;grid-template-columns:minmax(0,1fr) 1px minmax(0,1fr) 1px minmax(0,1fr);
           gap:0 20px;align-items:start}
  .avancadas{display:grid;grid-template-columns:minmax(0,1fr) 1px minmax(0,1fr) 1px
             minmax(0,1fr) 1px minmax(0,1fr);gap:0 22px;align-items:start}
  .risco{background:var(--border-sutil);align-self:stretch}

  /* o rótulo de cada coluna nasce no x da coluna que ele nomeia — por isso o
     `sec-rot` repete o `grid-template-columns` da faixa que encabeça. */
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);
           margin-bottom:8px;height:17px;display:grid;gap:0 22px;align-items:center}
  .sec-rot > span{display:flex;align-items:center;gap:8px;min-width:0;white-space:nowrap}
  .sr-status3{grid-template-columns:minmax(0,1fr)}
  .sr-avancadas{grid-template-columns:minmax(0,1fr) 1px minmax(0,1fr) 1px
                minmax(0,1fr) 1px minmax(0,1fr)}
  /* A LINHA DO TÍTULO DA SEÇÃO 3 LEVA O «Copiar» E O «Salvar», que são mais altos que os 17px
     de um rótulo: ela mede o que tem dentro, e a borda de cima fica nela. */
  .sr-log{grid-template-columns:minmax(0,1fr) auto;height:auto}
  .sr-log > span:last-child{gap:6px}
  /* NENHUMA FAIXA ENCOLHE — o quadro é `estica` e o corpo é uma coluna flex:
     sem isto o navegador espreme os rótulos para dar altura ao registro. Quem
     cresce e encolhe é só o `.registro`. */
  .quadro-corpo > *{flex-shrink:0}
  /* o título da seção 2 — o nome que o usuário deu, uma linha acima dos quatro rótulos.
     A LETRA É A DO «Sistema», e o pedido é de produto (25/09/2026, 22h13):
     *«Configurações avançadas — Escreve com a mesma cor e tamanho de Sistema»*.
     Quem pinta é o `.quadro-titulo` do topo, no `<span>` de dentro; aqui fica
     só o lugar: o vão e o risco de cima. */
  .sec-grupo{margin:14px 0 8px;padding-top:10px;border-top:1px solid var(--border-sutil)}
  .sec-alta{margin-top:14px;padding-top:10px;border-top:1px solid var(--border-sutil)}

  /* AS LINHAS DO STATUS E DO EXAME SÃO A MESMA PEÇA — pedido: *«no MESMO
     estilo das linhas do O exame de hoje (a pílula à esquerda e o texto
     curto)»*. 25,5px por linha, e duas linhas em cada uma das três colunas:
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
  /* SEM AVISO VERDE (conferência de 14/10/2026): o que está bem fica numa pílula neutra, na cor
     do texto; o laranja pede atenção e o vermelho é a linha que FALHA, até se curar. */
  .selo.ok{background:transparent;color:var(--texto-suave);box-shadow:inset 0 0 0 1px var(--border-forte)}
  .selo.aviso{background:var(--orange);color:var(--app-bg)}
  .selo.nt{background:var(--comment);color:var(--app-bg)}
  .selo.falha{background:var(--red);color:var(--app-bg)}
  .saude .txt{flex:1;display:flex;align-items:center;gap:7px;min-width:0}
  .saude .txt span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  /* A LINHA QUE LEVA A OUTRO LUGAR (a do Bluetooth, para a seção do rádio da
     aba Conexões) é um `<a>` inteiro: a mão vira e a linha acende no hover. */
  a.saude.vai{cursor:pointer}
  a.saude.vai:hover .txt{color:var(--fg)}
  /* O EXAME ENTRA NA GRADE DO STATUS: o produto troca o conteúdo de `.saude-cols` (duas colunas
     e o risco entre elas) e as duas viram as colunas 2 e 3 de `.status3`, na mesma largura. */
  .saude-cols{display:contents}
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
  /* a caixa do botão que pode ficar cinza: a altura é a mesma nos dois estados (régua 8). */
  .acao{display:flex;align-items:center}
  .coluna .acao > .btn{flex:1;min-width:0;width:auto}
  /* O BOTÃO DO SERVIÇO TEM DUAS CORES, e quem escolhe é o produto: vermelho
     quando o clique PARA, verde quando ele DEVOLVE o serviço (a pausa ativa,
     ou ele parado). A classe `verde` é acesa pelo campo que o pacote escreve
     todo tique; a regra de baixo só a deixa vencer o vermelho. */
  .btn.vermelho.verde{color:var(--green)}
  .btn.vermelho.verde:hover{border-color:var(--green);color:var(--green)}
  /* O «Restaurar de fábrica» é o único com a borda vermelha: o clique que perde o ajuste. */
  .btn.borda-vermelha{border-color:var(--red);color:var(--red)}
  .btn.borda-vermelha:hover{background:rgba(255,85,85,.08)}

  /* O PERFIL GLOBAL DE BATERIA E O TAMANHO DA INTERFACE, NA VERTICAL — os três botões da aba
     Vibração (`.seg`), empilhados, na altura dos botões vizinhos. Escolha única: o aceso
     é o `on`, e o nome de cada um vem do produto. */
  .seg.bat-perfis{flex-direction:column;flex-wrap:nowrap;gap:6px}
  .seg.bat-perfis button{flex:0 0 var(--h-acao);height:var(--h-acao);min-width:0;
                         padding:0 8px;overflow:hidden;text-overflow:ellipsis;
                         white-space:nowrap}

  /* A SAÚDE DO APP É UMA COLUNA DE TRÊS: os dois interruptores e o «Restaurar de fábrica», nas
     três alturas das vizinhas. */
  .saude-app{display:grid;grid-template-columns:minmax(0,1fr);grid-auto-flow:row;
             grid-template-rows:repeat(3,var(--h-acao));gap:6px 8px;min-width:0}
  .saude-app .cadeado,.saude-app .btn{width:100%;min-width:0;padding:0 10px;overflow:hidden;
                                      text-overflow:ellipsis}
  .saude-app .btn{justify-content:center}

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

  /* OS DETALHES TÉCNICOS OCUPAM O QUE SOBRA — pedido: *«ganhar altura pra
     ocupar melhor esse espaço abaixo dele. e ser mais fácil de ser lido»*.
     A seção cresce com o quadro (`estica`), e a caixa é ABSOLUTA dentro dela:
     um filho absoluto não conta para a altura do pai, então o registro vivo,
     com as suas oitenta linhas, ROLA POR DENTRO em vez de empurrar a página
     (a cura da ROLAGEM-01, de 09/09, continua a mesma).

     O REGISTRO É A ÚNICA FAIXA QUE ENCOLHE, E ATÉ ZERO — 15/10/2026 (T5). Era
     `flex:1 1 auto` com piso de 120px: em 1212x700 o fundo do registro passava 50px do quadro.
     `flex:1 1 0` com `min-height:0` devolve ao registro só o que sobrou das outras faixas.

     A LINHA QUEBRA, E NÃO SAI PELA DIREITA — 25/09/2026. Era `pre`, e a linha
     do journal (uns 200 caracteres) saía cortada: para ler uma linha inteira
     era preciso rolar de lado, e o usuário pediu o painel «mais fácil de ser lido».
     `pre-wrap` guarda as quebras do texto e dobra o que não cabe. */
  .registro{flex:1 1 0;min-height:0;position:relative}
  .registro > .log{position:absolute;top:0;right:0;bottom:0;left:0}
  .log{padding:10px 12px;border:1px solid var(--border-sutil);border-radius:7px;
       background:var(--app-bg);font-family:'JetBrains Mono',monospace;font-size:11px;
       line-height:1.6;color:var(--texto-suave);overflow:auto;white-space:pre-wrap;
       overflow-wrap:anywhere}
  .sec-rot .btn.copiar{height:22px;padding:0 12px;font-size:11.5px}
""" + CSS_GLIFO



LIGAVEIS = (
    ("Permitir correções automáticas", "correcoes-automaticas", CAMPO_DAS_CORRECOES, True,
     "Fixa o Proton, corrige o Vulkan e prepara cada jogo novo"),
    ("Iniciar com o sistema", "autostart", "hefesto-autostart", True,
     "Liga o serviço junto com o computador"),
)


def ligavel(rotulo, gesto, campo, ligado, dica):
    """A pílula que liga e desliga — a do «Modo Freestyle», com o endereço do produto."""
    return (f'            <button class="cadeado{" ligada" if ligado else ""}"'
            f' data-dica="{dica}" data-gesto="{_gesto(gesto)}"'
            f' data-campo="{_id(campo)}" data-hef-alvo="classe"'
            f' data-hef-classe="ligada"><span class="p"></span>{rotulo}</button>')


def linha(selo, cls, g, txt, ident="", href="", dica=""):
    """Uma linha do Status ou do exame — a MESMA peça, na marcação do produto."""
    tag = "a" if href else "div"
    vai = " vai" if href else ""
    i = f' data-id="{ident}"' if ident else ""
    h = f' href="{href}"' if href else ""
    t = f' data-dica="{dica}"' if dica else ""
    return (f'            <{tag} class="saude{vai}"{i}{h}>'
            f'<span class="selo {cls}"><span class="sg">{g}</span>{selo}</span>'
            f'<span class="txt"{t}><span>{txt}</span></span></{tag}>')


def item(rotulo, diz, cls="btn", gesto="", em_voo="", extra=""):
    """Um botão com o que ele faz na dica curta da casa."""
    g = f' data-gesto="{gesto}"' if gesto else ""
    v = f' data-hef-em-voo="{em_voo}"' if em_voo else ""
    return f'''            <button class="{cls}" data-dica="{diz}"{g}{v}{extra}>{rotulo}</button>'''


def item_escondido(rotulo, diz, gesto, campo, cls="btn"):
    """Um botão que o desenho tem e a tela só mostra quando o produto manda."""
    return (f'            <button class="{cls} so-avulso" data-dica="{diz}"'
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


def _dica_da_bateria(p):
    """O que o perfil impõe, curto; o perfil sem teto próprio manda escolher em cada aba."""
    return impoe(p) if p in _COM_TETO or p == PERFIL_DA_MESA else "Você escolhe em cada aba"


def _botoes_bateria():
    return "".join(
        f'<button class="{"on" if p == PERFIL_DA_MESA else ""}"'
        f' data-gesto="{_gesto("perfil-da-mesa")}" data-v="{p}"'
        f' data-campo="{_id("bateria-perfil")}" data-hef-alvo="classe"'
        f' data-hef-classe="on" data-hef-quando="{p}"'
        f' data-dica="{_dica_da_bateria(p)}">{ROT_PERFIL[p]}</button>'
        for p in ORC["PERFIS"])


def _botoes_tamanho():
    """Os tamanhos da interface: o aceso vem do produto, e o de hoje (100) nasce aceso."""
    return "".join(
        f'<button class="{"on" if v == 100 else ""}"'
        f' data-gesto="{_gesto("tamanho-da-interface")}" data-v="{v}"'
        f' data-campo="{_id(CAMPO_DO_TAMANHO)}" data-hef-alvo="classe"'
        f' data-hef-classe="on" data-hef-quando="{v}"'
        f' data-dica="{dica}">{rotulo}</button>'
        for v, rotulo, dica in TAMANHOS_DA_INTERFACE)


# (`interface/sistema.status_do_*`) — o teste da forma compara as duas.
_NO_RADIO = len(BT)
STATUS = [
    linha("LIGADO", "ok", "✓", "Serviço", ident="hefesto-estado",
          dica="Roda por trás e volta sozinho se travar."),
    linha("LIGADO", "ok", "✓", "Troca de perfil ao abrir o jogo",
          ident="hefesto-troca-de-perfil",
          dica="O perfil do jogo entra sozinho quando ele abre."),
]

#: As quatro linhas do exame que ficam à vista (o desenho do todo): o Bluetooth leva à aba
#: Conexões. Qualquer outra linha do exame só aparece se FALHAR, e então em vermelho.
ACHADOS = [
    linha("OK", "ok", "✓",
          f"Bluetooth: 1 adaptador · {_NO_RADIO} "
          f"{'controle' if _NO_RADIO == 1 else 'controles'}",
          ident="status-bluetooth", href="08-conexoes.html#rd-secao",
          dica="Clique para ver os adaptadores na aba Conexões."),
    linha("OK", "ok", "✓", "Steam Input desligado",
          dica="Steam Input desligado para o DualSense"),
    linha("OK", "ok", "✓", "Áudio roteado", dica=f"Áudio dos {N} controles roteado"),
    linha("OK", "ok", "✓", "Um gamepad virtual por jogador",
          dica="Um gamepad virtual por jogador"),
]
MEIO = len(ACHADOS) // 2 + len(ACHADOS) % 2

#: Os rótulos de cada coluna e a dica curta de cada um (o desenho do todo): nenhum «?».
DICA_DO_TITULO = "Esta aba é do computador, não de um controle"
DICA_DO_STATUS = "Linha que falha fica vermelha até se curar"
DICA_DO_FUNCIONAMENTO = "Parar desliga o serviço inteiro, não só o jogo"
DICA_DA_INTERFACE = "O tamanho das letras e dos botões, em toda aba"
DICA_DA_BATERIA = "Vale para todos; cada controle pode ter o seu em Conexões"
DICA_DA_SAUDE = "Verde é ligado. Clique para trocar"
DICA_DO_REGISTRO = "O registro do serviço; copie para relatar um problema"

ROTULO_ATUALIZAR = "Atualizar"
EM_VOO_ATUALIZAR = "Atualizando…"
DICA_ATUALIZAR = "Relê os atalhos e os arquivos da Steam"

ROTULO_PARAR = "Parar"

MIOLO = f'''
    <div class="quadro estica">
      <div class="quadro-topo">
        <span class="quadro-titulo" data-dica="{DICA_DO_TITULO}">Sistema</span>
      </div>
      <div class="quadro-corpo">

        <!-- ---------- 1. STATUS: SEIS LINHAS, EM TRÊS COLUNAS ---------- -->
        <!-- O Status leva as duas primeiras; o exame, as quatro seguintes, em duas colunas. O que
             não está aqui só aparece se FALHAR, e então em vermelho até se curar. -->
        <div class="sec-rot sr-status3">
          <span data-dica="{DICA_DO_STATUS}">Status</span>
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
        <div class="sec-grupo"><span class="quadro-titulo">Configurações avançadas</span></div>
        <div class="sec-rot sr-avancadas">
          <span data-dica="{DICA_DO_FUNCIONAMENTO}">Funcionamento do app</span><span></span>
          <span data-dica="{DICA_DA_INTERFACE}">Interface</span><span></span>
          <span data-dica="{DICA_DA_BATERIA}">Perfil global de bateria</span><span></span>
          <span data-dica="{DICA_DA_SAUDE}">Saúde do app</span>
        </div>
        <div class="avancadas">
          <div class="coluna col-servico">
{item(ROTULO_PARAR, "Os controles viram gamepads comuns. Pergunta antes", "btn vermelho", gesto=_gesto("parar-ou-retomar"), extra=f' data-campo="{CAMPO_DO_VERDE}" data-hef-alvo="classe" data-hef-classe="verde"')}
{item(ROTULO_ATUALIZAR, DICA_ATUALIZAR, gesto=_gesto("atualizar"), em_voo=EM_VOO_ATUALIZAR)}
{item_escondido("Corrigir o serviço", "Faz o serviço subir do jeito certo", "corrigir-modo", CAMPO_DO_MODO_AVULSO)}
{item_cinza("Reiniciar", "Para e liga de novo; nenhum ajuste se perde", "reiniciar")}
          </div>
          <div class="risco"></div>
          <div class="coluna">
            <div class="seg bat-perfis" data-id="{_id(CAMPO_DO_TAMANHO)}">{_botoes_tamanho()}</div>
          </div>
          <div class="risco"></div>
          <div class="coluna">
            <div class="seg bat-perfis" data-id="{_id("bateria-perfil")}">{_botoes_bateria()}</div>
          </div>
          <div class="risco"></div>
          <div class="coluna saude-app">
{chr(10).join(ligavel(*x) for x in LIGAVEIS)}
{item("Restaurar de fábrica", "Volta ao padrão; seus perfis salvos ficam. Pergunta antes", "btn vermelho borda-vermelha", gesto=_gesto("restaurar-de-fabrica"))}
          </div>
        </div>

        <!-- ---------- 3. DETALHES TÉCNICOS ---------- -->
        <div class="sec-rot sr-log sec-alta">
          <span data-dica="{DICA_DO_REGISTRO}">Detalhes técnicos</span>
          <span>{item("Copiar", "Copia o registro inteiro", "btn copiar", gesto=_gesto("copiar-registro")).strip()}{item("Salvar", "Guarda o registro num arquivo", "btn copiar", gesto=_gesto("salvar-registro")).strip()}</span>
        </div>
        <div class="registro">
          <div class="log" data-id="{_id("registro-texto")}" data-campo="{_id("registro-texto")}" data-hef-rolar="fim">[23:41:02] daemon pronto · {N} controles · {N} gamepads virtuais · controle virtual ok
[23:41:02] {" · ".join(f'{c["nome"]} {c["via"].lower()}' for c in CONECTADOS)} · fw 0x0356 nos {N} · cor de fábrica lida nos {N}
[23:41:07] exame: steam input desligado em 2 jogos · proton 9.0-4 fixado em 3
[23:41:09] perfil "Mortal Kombat" aplicado aos {N} · gatilho L2 escrito, sem leitura de volta
[23:41:12] rádio: 1 adaptador · {_NO_RADIO} {'controle' if _NO_RADIO == 1 else 'controles'} · sem fila
[23:41:15] janela da frente: steam_app_1971870 · perfil "Mortal Kombat" mantido</div>
        </div>

      </div>
    </div>
'''

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
H_ACAO = _token(_TOPO, "--h-acao")


_ESCONDE_O_AVULSO = ".so-avulso:not(.mostra){display:none}" in CSS
_COLUNAS = re.findall(r'<div class="coluna[^"]*">(.*?)\n          </div>\n',
                      _entre(MIOLO, '<div class="avancadas">', "3. DETALHES"), re.S)
if len(_COLUNAS) != 4:
    raise SystemExit(f"ERRO: a seção configurações avançadas tem {len(_COLUNAS)} "
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
    raise SystemExit(f"ERRO: as quatro colunas das configurações avançadas têm "
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

_ACOES_DO_SERVICO = _entre(MIOLO, '<div class="coluna col-servico">', '<div class="risco">')
_ROTULOS = {
    "a coluna": re.search(r'<div class="sec-rot sr-avancadas">\s*<span[^>]*>([^<]*)<',
                          MIOLO).group(1),
    "a linha do Status": re.search(
        r'data-id="hefesto-estado"[^>]*>.*?<span class="txt"[^>]*><span>([^<]*)</span>',
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

_SEM_GLIFO = re.findall(r'<span class="selo [a-z]+"><span class="sg">\s*</span>([^<]*)',
                        MIOLO)
_PILULAS = MIOLO.count('<span class="selo ')
if not _PILULAS:
    raise SystemExit("ERRO: nenhuma pílula no Status nem no exame — a régua do glifo "
                     "cegou, e seletor que casa ZERO é erro, não silêncio.")
if _SEM_GLIFO:
    raise SystemExit("ERRO: pílula sem glifo: " + " · ".join(repr(r) for r in _SEM_GLIFO))

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

_BOTOES_BAT = re.findall(r'<button class="(on)?"[^>]*data-v="([^"]+)"[^>]*>([^<]+)</button>',
                         _entre(MIOLO, '<div class="seg bat-perfis" data-id="bateria-perfil"', "</div>"))
if len(_BOTOES_BAT) != len(ORC["PERFIS"]):
    raise SystemExit(f"ERRO: o perfil de bateria tem {len(_BOTOES_BAT)} botões e o produto "
                     f"declara {len(ORC['PERFIS'])} perfis — a tela deixou de mostrar todos.")
for _on, _p, _rot in _BOTOES_BAT:
    if _rot != ROT_PERFIL[_p]:
        raise SystemExit(f"ERRO: o botão de {_p!r} diz {_rot!r} e o produto o chama de "
                         f"{ROT_PERFIL[_p]!r} — nome de perfil não se digita nesta tela.")
if sum(1 for on, _, _ in _BOTOES_BAT if on) != 1:
    raise SystemExit("ERRO: a escolha do perfil de bateria não é única — ela pediu "
                     '"três botões lado a lado com escolha única".')
_BOTOES_TAMANHO = re.findall(
    r'<button class="(on)?"[^>]*data-v="([^"]+)"[^>]*>([^<]+)</button>',
    _entre(MIOLO, f'<div class="seg bat-perfis" data-id="{CAMPO_DO_TAMANHO}"', "</div>"))
if [(int(v), r) for _o, v, r in _BOTOES_TAMANHO] != [(v, r) for v, r, _d in TAMANHOS_DA_INTERFACE]:
    raise SystemExit("ERRO: os botões do tamanho da interface não são os do produto "
                     f"({_BOTOES_TAMANHO}) — o nome e o valor vêm de TAMANHOS_DA_INTERFACE.")
if sum(1 for on, _, _ in _BOTOES_TAMANHO if on) != 1:
    raise SystemExit("ERRO: a escolha do tamanho da interface não é única.")
if '<span class="rot">O perfil da mesa' in MIOLO:
    raise SystemExit('ERRO: o rótulo "O perfil da mesa" voltou (ponto 7.1 dela).')


for _faixa in (".status3", ".avancadas"):
    _r = re.search(re.escape(_faixa) + r"\{[^}]*grid-template-columns:([^;]*);", CSS)
    if not _r:
        raise SystemExit(f"ERRO: a faixa `{_faixa}` sumiu ou deixou de declarar colunas — "
                         "a régua do estouro ficou cega.")
    if re.search(r"(^|\s)[12]fr", _r.group(1)):
        raise SystemExit(f"ERRO: a faixa `{_faixa}` voltou a usar `fr` cru: "
                         f"`{_r.group(1).strip()}`. O piso é o CONTEÚDO, e a coluna "
                         "sai do limite da janela. Use `minmax(0,1fr)`.")


_CINZAS = ("reiniciar",)
for _g in _CINZAS:
    _campo = f"{_g}{SUFIXO_DA_RAZAO}"
    _btn = re.search(
        r'<button class="[^"]*"[^>]*data-campo="' + re.escape(_campo) + r'"[^>]*>',
        MIOLO)
    if not _btn:
        raise SystemExit(f"ERRO: o botão de {_g!r} perdeu o endereço `{_campo}`.")
    for _exigido in ('data-hef-alvo="classe"', 'data-hef-classe="apagado"',
                     'data-hef-atributo="aria-disabled"', 'data-hef-razao="sim"',
                     f'data-gesto="{_g}"'):
        if _exigido not in _btn.group(0):
            raise SystemExit(f"ERRO: o botão de {_g!r} perdeu `{_exigido}` — a peça "
                             "da D-03 é inteira (a razão mora no `data-dica` dele).")

if "ajuda" in re.findall(r'class="([^"]*)"', MIOLO):
    raise SystemExit("ERRO: o «?» voltou: a explicação de cada rótulo é o `data-dica` dele "
                     "(A1 do desenho do todo, 13/10/2026).")
if MIOLO.count(f'data-gesto="{_gesto("correcoes-automaticas")}"') != 1:
    raise SystemExit("ERRO: o interruptor das correções automáticas tem de ser UM só botão.")
for _morto in ("refazer-consertos", "aplicar-aos-jogos", "fixar-proton", "corrigir-vulkan",
               "doctor"):
    if f'data-gesto="{_morto}"' in MIOLO:
        raise SystemExit(f"ERRO: o botão `{_morto}` voltou: o interruptor das correções "
                         "automáticas junta o Doctor, os lançadores, o Proton e o Vulkan.")
if not re.search(r"\.registro\{[^}]*min-height:0", CSS):
    raise SystemExit("ERRO: o registro deixou de poder encolher até zero — em 1212x700 o "
                     "fundo dele passaria do quadro.")
if 'class="ajuda porque"' in MIOLO:
    raise SystemExit("ERRO: o `?` da razão voltou: a razão do botão cinza é o `data-dica` dele.")

# 9. O BOTÃO DO `daemon.reload` SE CHAMA "ATUALIZAR" PORQUE O USUÁRIO MANDOU (09-Q1),
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
    """Monta a página e a GRAVA em `mockup/09-sistema.html`. Só do `__main__`."""
    n = monta("09-sistema", "Sistema", MIOLO, CSS)

    p = onde.pagina("09-sistema.html")
    s = p.read_text()

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

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-09-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    escrever_a_bancada()
    shutil.copyfile(_prova / "09-sistema.html", _real / "09-sistema.html")
    shutil.rmtree(_prova)
