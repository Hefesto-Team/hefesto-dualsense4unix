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

from hefesto_dualsense4unix.integrations.camadas_vulkan import (  # noqa: E402
    frase_do_estado as _frase_do_vulkan,
)

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
    {"APELIDO_NA_TELA", "CAMPO_DO_MODO_AVULSO", "CAMPO_DO_STATUS", "CAMPO_DO_VERDE"})
APELIDO_NA_TELA = _DO_PACOTE["APELIDO_NA_TELA"]
CAMPO_DO_MODO_AVULSO = _DO_PACOTE["CAMPO_DO_MODO_AVULSO"]
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
    raise SystemExit("ERRO: a frase do Perfil de Bateria afirma que UM perfil põe teto, "
                     f"e agora são {len(_COM_TETO)}: {_COM_TETO}. Reescreva a frase.")
_SO_ESTE = _COM_TETO[0]


def impoe(perfil):
    """O que o perfil escolhido impõe — o valor curto da linha de estado."""
    forca = forca_do_perfil(perfil)
    return f"Vibração em {forca}" if forca else "Nada é limitado"


CSS = """
  /* ---------- Sistema, em três seções (A-09-SISTEMA-EM-TRES-SECOES-01, 25/09/2026) ----------
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
  /* o título da seção 2 — o nome que ela deu, uma linha acima dos quatro rótulos.
     A LETRA É A DO «Sistema», e o pedido é de produto (25/09/2026, 22h13):
     *«Configurações Avançadas — Escreve com a mesma cor e tamanho de Sistema»*.
     Quem pinta é o `.quadro-titulo` do topo, no `<span>` de dentro; aqui fica
     só o lugar: o vão e o risco de cima. */
  .sec-grupo{margin:14px 0 8px;padding-top:10px;border-top:1px solid var(--border-sutil)}
  .sec-alta{margin-top:14px;padding-top:10px;border-top:1px solid var(--border-sutil)}

  /* AS LINHAS DO STATUS E DO EXAME SÃO A MESMA PEÇA —  25,5px por linha, e quatro linhas em cada uma das três colunas:
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

  /* OS DETALHES TÉCNICOS OCUPAM O QUE SOBRA
     A seção cresce com o quadro (`estica`), e a caixa é ABSOLUTA dentro dela:
     um filho absoluto não conta para a altura do pai, então o registro vivo,
     com as suas oitenta linhas, ROLA POR DENTRO em vez de empurrar a página
     (a cura da ROLAGEM-01, de 09/09, continua a mesma). O piso guarda que ela
     nunca caia abaixo de seis linhas.

     A LINHA QUEBRA, E NÃO SAI PELA DIREITA — 25/09/2026. Era `pre`, e a linha
     do journal (uns 200 caracteres) saía cortada: para ler uma linha inteira
     era preciso rolar de lado, e o usuário pediu o painel «mais fácil de ser lido».
     `pre-wrap` guarda as quebras do texto e dobra o que não cabe. */
  .registro{flex:1 1 auto;flex-shrink:1;min-height:120px;position:relative}
  .registro > .log{position:absolute;top:0;right:0;bottom:0;left:0}
  .log{padding:10px 12px;border:1px solid var(--border-sutil);border-radius:7px;
       background:var(--app-bg);font-family:'JetBrains Mono',monospace;font-size:11px;
       line-height:1.6;color:var(--texto-suave);overflow:auto;white-space:pre-wrap;
       overflow-wrap:anywhere}
  .sec-rot .btn.copiar{height:22px;padding:0 12px;font-size:11.5px}
""" + CSS_GLIFO


#: A DICA DO «Corrigir Vulkan» DIZ O QUE ELE FAZ E O PREÇO — 28/09/2026,
LIGAVEIS = (
    ("Iniciar com o sistema", "autostart", "hefesto-autostart", True,
     "Liga o serviço junto com o computador. Clique para trocar."),
    ("Fixar Proton", "fixar-proton", "proton-fixado", True,
     "Mantém os jogos na versão do Proton que faz o controle vibrar e tocar "
     "som, e leva à lixeira as versões que nenhum jogo usa. Clique para "
     "trocar, com a Steam fechada."),
    ("Corrigir Vulkan", "corrigir-vulkan", "vulkan-corrigido", False,
     "Tira dos jogos a sobreposição e o gravador de shaders da Steam. Sem "
     "eles, o Shift+Tab da Steam some e ela não guarda os shaders do jogo. "
     "Vale no próximo jogo que abrir."),
)


def ligavel(rotulo, gesto, campo, ligado, dica):
    """A pílula que liga e desliga — a do «Modo Freestyle», com o endereço do produto."""
    return (f'            <button class="cadeado{" ligada" if ligado else ""}"'
            f' title="{dica}" data-gesto="{_gesto(gesto)}"'
            f' data-campo="{_id(campo)}" data-hef-alvo="classe"'
            f' data-hef-classe="ligada"><span class="p"></span>{rotulo}</button>')


def linha(selo, cls, g, txt, ident="", href="", title=""):
    """Uma linha do Status ou do exame — a MESMA peça, na marcação do produto."""
    tag = "a" if href else "div"
    vai = " vai" if href else ""
    i = f' data-id="{ident}"' if ident else ""
    h = f' href="{href}"' if href else ""
    t = f' title="{title}"' if title else ""
    return (f'            <{tag} class="saude{vai}"{i}{h}>'
            f'<span class="selo {cls}"><span class="sg">{g}</span>{selo}</span>'
            f'<span class="txt"{t}><span>{txt}</span></span></{tag}>')


def item(rotulo, diz, cls="btn", gesto="", em_voo="", extra=""):
    """Um botão com o que ele faz no `title` — pedido em 27/08."""
    g = f' data-gesto="{gesto}"' if gesto else ""
    v = f' data-hef-em-voo="{em_voo}"' if em_voo else ""
    return f'''            <button class="{cls}" title="{diz}"{g}{v}{extra}>{rotulo}</button>'''


def item_escondido(rotulo, diz, gesto, campo, cls="btn"):
    """Um botão que o desenho tem e a tela só mostra quando o produto manda."""
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


def _botoes_bateria():
    return "".join(
        f'<button class="{"on" if p == PERFIL_DA_MESA else ""}"'
        f' data-gesto="{_gesto("perfil-da-mesa")}" data-v="{p}"'
        f' data-campo="{_id("bateria-perfil")}" data-hef-alvo="classe"'
        f' data-hef-classe="on" data-hef-quando="{p}"'
        f' title="{ROT_PERFIL[p]}: {impoe(p).lower()}. Vale para todos os controles'
        f'{"." if p in _COM_TETO else " — cada um pode ter o seu na aba Conexões."}">'
        f'{ROT_PERFIL[p]}</button>'
        for p in ORC["PERFIS"])


# (`interface/sistema.status_do_*`) — o teste da forma compara as duas.
_NO_RADIO = len(BT)
STATUS = [
    linha("LIGADO", "ok", "✓", "Serviço", ident="hefesto-estado",
          title="Roda por trás e volta sozinho se travar."),
    linha("LIGADO", "ok", "✓", "Troca de perfil ao abrir o jogo",
          ident="hefesto-troca-de-perfil",
          title="O perfil do jogo entra sozinho quando ele abre."),
    linha("NOTA", "nt", "i", "Ambiente gráfico: Wayland · COSMIC",
          ident="hefesto-ambiente",
          title="É por ele que o Hefesto vê qual janela está na frente."),
    linha("OK", "ok", "✓",
          f"Bluetooth: 1 adaptador · {_NO_RADIO} "
          f"{'controle' if _NO_RADIO == 1 else 'controles'}",
          ident="status-bluetooth", href="08-conexoes.html#rd-secao",
          title="Clique para ver os adaptadores na aba Conexões."),
]

_VULKAN_ACESO = next(lig for _r, g, _c, lig, _d in LIGAVEIS if g == "corrigir-vulkan")
FRASE_DO_VULKAN = _frase_do_vulkan(_VULKAN_ACESO)
ACHADOS = [
    linha("OK", "ok", "✓", "Regra de permissão dos controles instalada",
          title="Regra de permissão dos controles instalada"),
    linha("OK", "ok", "✓", "O serviço sobe sozinho no login",
          title="O serviço sobe sozinho no login"),
    linha("OK", "ok", "✓", "Steam Input desligado para o DualSense",
          title="Steam Input desligado para o DualSense"),
    linha("OK", "ok", "✓", f"Áudio dos {N} controles roteado",
          title=f"Áudio dos {N} controles roteado"),
    linha("NOTA", "nt", "i", "Um gamepad virtual por jogador",
          title="Um gamepad virtual por jogador"),
    linha("NOTA", "nt", "i", "Proton fixado em 9.0-4 para 3 jogos",
          title="Proton fixado em 9.0-4 para 3 jogos"),
    linha("NOTA", "nt", "i", "Som do sistema: sai em Controle 1",
          title="Som do sistema: sai em Controle 1"),
    linha("NOTA", "nt", "i", FRASE_DO_VULKAN, title=FRASE_DO_VULKAN),
]
MEIO = len(ACHADOS) // 2 + len(ACHADOS) % 2

D_STATUS = ('<span class="ajuda">?<span class="dica">'
            'Como o Hefesto está agora neste computador. A pílula diz o estado.'
            '</span></span>')
D_SERVICO = ('<span class="ajuda">?<span class="dica">'
             'Parar aqui não é o mesmo que desligar o Hefesto na aba Jogar: lá ele '
             'só sai do meio do jogo.'
             '</span></span>')
D_BATERIA = ('<span class="ajuda">?<span class="dica">'
             'Vale para todos os controles, e cada um pode ter o seu na aba Conexões.'
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

ROTULO_ATUALIZAR = "Atualizar"
EM_VOO_ATUALIZAR = "Atualizando…"
DICA_ATUALIZAR = ("Manda o serviço reler os atalhos do controle e os arquivos "
                  "que a Steam usa para abrir os jogos. Leva alguns segundos.")

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

        <!-- ---------- 1. STATUS + O EXAME ---------- -->
        <!-- O RÓTULO DO EXAME E A CONTAGEM SAÍRAM, E O LUGAR FICA VAZIO — pedido, 25/09/2026, 22h13: «remove o exame de hoje e tooltip dele» e
             «Remove esse 8 linhas deixa o espaço vazio». O `<span>` vazio segura
             a terceira faixa: nada sobe, e o exame continua onde estava. -->
        <div class="sec-rot sr-status3">
          <span>Status {D_STATUS}</span><span></span><span></span>
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
        <div class="sec-grupo"><span class="quadro-titulo">Configurações Avançadas</span></div>
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
{item("Reaplicar correções automáticas", "Desliga o Steam Input onde ele atrapalha e leva à lixeira as versões do Proton que nenhum jogo usa. Sem senha, sem fechar nada, e com cópia de segurança.", gesto=_gesto("refazer-consertos"))}
{item("Aplicar soluções nos lançadores", "Põe o Hefesto nos jogos da Steam e dos outros lançadores, sem perder as suas opções. Pergunta antes: fecha a Steam por uns 20 segundos.", gesto=_gesto("aplicar-aos-jogos"))}
{item("Restaurar de fábrica", "Devolve o perfil de fábrica e o padrão do computador. Pergunta antes, e os seus perfis salvos ficam.", "btn vermelho", gesto=_gesto("restaurar-de-fabrica"))}
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
[23:41:02] {" · ".join(f'p{c["jogador"]} {c["via"].lower()}' for c in CONECTADOS)} · fw 0x0356 nos {N} · cor de fábrica lida ({", ".join(f'p{c["jogador"]}' for c in CONECTADOS)})
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
      com menos texto e mais gesto. <!-- noqa-acento: citação literal --></li>
    <li><b>1. Status</b> — o antigo <i>O serviço</i> virou <b>Status</b>, com quatro linhas na
      forma do exame (a pílula e o texto curto): <b>Serviço</b> (LIGADO, PAUSADO ou PARADO — a
      pausa deixou de ter linha própria), <b>Troca de perfil</b>, <b>Ambiente gráfico</b> e
      <b>Bluetooth</b>, que leva à seção do rádio da aba Conexões. O exame fica ao lado, em duas
      colunas, e o Bluetooth saiu dele. As frases do exame saem curtas; a inteira fica no
      <code>title</code>. As linhas do Status não têm <code>?</code>: a frase de cada uma fica no
      <code>title</code>, e o exame não tem rótulo nem contagem — o lugar fica vazio (os ajustes
      dela das 22h13).</li>
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

_ACOES_DO_SERVICO = _entre(MIOLO, '<div class="coluna col-servico">', '<div class="risco">')
_ROTULOS = {
    "a coluna": re.search(r'<div class="sec-rot sr-avancadas">\s*<span>([^<]*)<',
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


for _faixa in (".status3", ".avancadas", ".saude-cols"):
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
                     'data-hef-atributo="aria-disabled"', f'data-gesto="{_g}"'):
        if _exigido not in _btn.group(0):
            raise SystemExit(f"ERRO: o botão de {_g!r} perdeu `{_exigido}` — a peça "
                             "da D-03 é inteira.")
    if not re.search(r'<span class="dica" data-campo="' + re.escape(_campo)
                     + r'" data-hef-alvo="html">', MIOLO):
        raise SystemExit(f"ERRO: o `?` de {_g!r} não recebe `{_campo}` pelo alvo `html`.")

_PORQUES = MIOLO.count('class="ajuda porque"')
_PORQUES_NA_CAIXA = sum(
    _bloco.count('class="ajuda porque"')
    for _bloco in re.findall(r'<div class="acao">.*?</div>\s*</div>', MIOLO, re.S))
if len(_CINZAS) != _PORQUES or _PORQUES_NA_CAIXA != _PORQUES:
    raise SystemExit(
        f"ERRO: esta página tem {_PORQUES} `?` de razão e {_PORQUES_NA_CAIXA} "
        f"deles dentro de uma `.acao` (esperados {len(_CINZAS)} nos dois).")

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
