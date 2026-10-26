import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import collections
import re
import onde
from monta import monta, glifo, cor_da_zona, rotulo, botao_cinza, CSS_GLIFO, MESA, SEPARADOR, R

sys.path.insert(0, str(R.parents[1]))
from hefesto_dualsense4unix.profiles.estilos_de_jogo import (
    ESTILOS as ESTILOS_DO_MOTOR,
)
from hefesto_dualsense4unix.profiles.schema import PRIORIDADE_MAXIMA
from hefesto_dualsense4unix.profiles.simple_match import (
    ROTULO_SO_QUANDO_ESCOLHER,
    SEPARADOR_DA_PROCEDENCIA,
)


SECOES = [
    ("leds", ("lightbar", "led-jogador")),
    ("triggers", ("l2", "r2")),
    ("rumble", ("rumble_esquerdo", "rumble_direito")),
    ("speaker", ("alto-falante",)),
    ("mic", ("mic",)),
    ("sensores", ("giroscopio", "acelerometro")),
    ("mascara", ("ps",)),
    ("movimento", ("stick_r",)),
    ("ativacao", ("cross",)),  # (noqa-acento)
    ("analogicos", ("stick_l",)),
]

NOME_DA_SECAO = {
    "leds": "luz",
    "triggers": "gatilhos",
    "rumble": "vibração",
    "speaker": "alto-falante",
    "mic": "microfone",
    "sensores": "sensores",
    "mascara": "máscara",
    "movimento": "comandos virtuais",
    "ativacao": "ativação dos botões",  # (noqa-acento)
    "analogicos": "curva dos analógicos",
}


def _lista_das_secoes() -> str:
    """`luz, gatilhos, vibração, alto-falante, microfone e sensores`."""
    nomes = [NOME_DA_SECAO[campo] for campo, _pecas in SECOES]
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}" if len(nomes) > 1 else nomes[0]


_EXTENSO = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis",
            7: "sete", 8: "oito", 9: "nove", 10: "dez", 11: "onze", 12: "doze",
            13: "treze", 14: "catorze", 15: "quinze", 16: "dezesseis",
            17: "dezessete", 18: "dezoito", 19: "dezenove", 20: "vinte"}
QUANTAS_SECOES = _EXTENSO[len(SECOES)]

GUARDA = {
    "p1": {"leds", "triggers", "rumble", "mic", "movimento"},
    "p2": {"leds", "rumble", "sensores"},
    "p3": {"leds", "mascara"},
    "p4": set(),
}

NAO_DIZ = "—"
AGORA = {
    "p1": {"triggers": NAO_DIZ, "mic": ""},
    "p2": {"triggers": NAO_DIZ, "leds": "", "movimento": ""},
    "p3": {"triggers": NAO_DIZ},
    "p4": {"triggers": NAO_DIZ},
}
DICA_DO_NAO_DIZ = "O controle não diz"
DICA_DA_MASCARA = "Máscara: {mascara}"
MASCARA_QUE_ACENDE = "DualSense"
DICA_DO_STATUS = "Aceso: ligado agora; o ponto: só deste controle"

ID_DA_PECA = {"p1": "AA:BB:CC:00:00:01", "p2": "AA:BB:CC:00:00:02",
              "p3": "AA:BB:CC:00:00:03", "p4": "AA:BB:CC:00:00:04"}

CSS = CSS_GLIFO + """  .perfis{flex:1;min-height:0;display:grid;grid-template-columns:1fr 1fr;align-items:stretch;
          border:1px solid var(--linha);border-radius:7px;background:var(--app-bg);
          overflow:hidden}
  .perfis > div{display:flex;flex-direction:column;padding:10px 14px;min-height:0;min-width:0}
  .perfis > div:first-child{padding-right:7px}
  .perfis > div:last-child{padding-left:7px}

  .perfis > div > .moldura{flex:1;min-height:0;display:flex;flex-direction:column}
  .moldura{border:none;background:none;padding:0}
  .sec-rot{font-size:12px;font-weight:700;color:var(--rot-campo);
           margin-bottom:10px;display:flex;align-items:center;gap:6px;height:15px}
  .lista{position:relative;flex:1;display:flex;min-height:0}
  .rolo{scroll-snap-type:y proximity}
  .rolo tr{scroll-snap-align:start}
  .rolo{flex:1;overflow-y:auto;border-radius:6px;
        background:var(--panel)}
  .rolo::-webkit-scrollbar{width:10px}
  .rolo::-webkit-scrollbar-track{background:transparent}
  .rolo::-webkit-scrollbar-thumb{background:var(--border-forte);border-radius:5px}
  .rolo::-webkit-scrollbar-thumb:hover{background:var(--comment)}
  .tab{width:100%;border-collapse:collapse;font-size:11.5px}
  .tab thead th{position:sticky;top:0;z-index:2;text-align:left;font-weight:700;font-size:10px;
          color:var(--fg);
          padding:7px 10px;background:var(--elevated);
          border-bottom:1px solid var(--linha)}
  .tab td{padding:8px 10px;color:var(--texto-suave);cursor:pointer;
          border-bottom:1px solid var(--linha)}
  .tab tbody tr:nth-child(even) td{background:rgba(255,255,255,.018)}
  .tab tbody tr:last-child td{border-bottom:none}
  .tab tr.ativo td{color:var(--green);font-weight:600}
  .tab tr.ativo td:first-child{box-shadow:inset 3px 0 0 var(--green)}
  .tab tbody tr[aria-selected="true"] td{background:rgba(189,147,249,.30);
          color:var(--fg);font-weight:600}
  .tab tbody tr[aria-selected="true"] td:first-child{box-shadow:inset 3px 0 0 var(--purple)}
  .tab tbody tr.ativo[aria-selected="true"] td{color:var(--green)}
  .tab tbody tr.ativo[aria-selected="true"] td:first-child{
          box-shadow:inset 3px 0 0 var(--green),inset 6px 0 0 var(--purple)}
  .tab tbody tr:hover:not(.ativo):not([aria-selected="true"]) td{
          background:rgba(255,255,255,.06)}
  .tab tbody tr.ativo:hover:not([aria-selected="true"]) td{
          background:rgba(255,255,255,.06)}
  .icone-rot{-webkit-appearance:none;appearance:none;border:none;background:none;
             padding:0;margin:-5px 0;width:24px;height:24px;flex:0 0 24px;
             display:inline-flex;align-items:center;justify-content:center;
             color:inherit;cursor:pointer;border-radius:5px;align-self:center}
  .icone-rot:hover{background:rgba(255,255,255,.09)}
  .icone-rot:active{background:rgba(255,255,255,.15)}
  .icone-rot.on{background:var(--sel-bg,rgba(189,147,249,.30))}
  .procura{-webkit-appearance:none;appearance:none;width:0;padding:0;border:none;
           background:var(--panel);color:var(--fg);font:inherit;font-weight:400;
           font-size:11px;border-radius:5px;min-width:0;
           transition:width .12s ease,padding .12s ease}
  .procura.on{width:150px;padding:3px 7px;border:1px solid var(--border-forte)}
  .procura::placeholder{color:var(--fg)}
  .fora-da-busca{font-size:10.5px;color:var(--fg);font-weight:400;
                 letter-spacing:0;text-transform:none;display:none}
  .fora-da-busca.on{display:inline}
  .ordena{pointer-events:none;font-size:10px;line-height:1;color:var(--purple)}
  .ordena[data-ordem]{margin-left:4px}
  .ordena[data-ordem="↑"]::after{content:"↑"}
  .ordena[data-ordem="↓"]::after{content:"↓"}
  .puxador{position:absolute;top:0;bottom:0;right:0;width:9px;z-index:3;
           cursor:col-resize;background:none}
  .puxador:hover{background:linear-gradient(90deg,transparent 3px,
                 var(--purple) 3px,var(--purple) 5px,transparent 5px)}
  .arrastando,.arrastando *{cursor:col-resize !important;user-select:none}
  .tab{table-layout:fixed}
  .tab td,.tab th{overflow:hidden;text-overflow:ellipsis}
  .tab tbody td{white-space:nowrap}
  .conta-perfis{font-size:10.5px;color:var(--fg);margin-left:auto;text-transform:none;
                letter-spacing:0}
  .campos{flex:1;min-height:0;border-radius:6px;
          background:var(--panel);
          padding:10px 12px;display:flex;flex-direction:column;justify-content:flex-start}
  .campo > span:first-child{color:var(--fg);font-weight:700;text-align:left;
                            white-space:nowrap}
  .campo{display:grid;grid-template-columns:var(--rot-p) minmax(0,1fr);align-items:center;gap:12px;
         height:var(--h-escolha);font-size:12px;color:var(--fg);margin-bottom:4px}

  .campo .val{display:flex;align-items:center;gap:10px}
  .campo input[type=text],.campo select{
    flex:1;min-width:0;height:var(--h-escolha);border-radius:7px;font-size:12.5px;font-family:inherit;
    padding:0 11px;border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
  }
  .campo select{cursor:pointer}
  .campo select.destaque{border-color:var(--purple);background:var(--sel-bg);font-weight:600}
  .campo .btn{flex:0 0 auto;white-space:nowrap}
  :root{--rot-p:86px}

  .desfecho{padding:0 14px;margin-top:0;height:0;line-height:15px;
            font-size:11px;color:var(--green);
            display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
            overflow:hidden;
            visibility:hidden}
  .desfecho.on{visibility:visible;margin-top:7px;height:30px}

  .campo .exige{
    display:none;flex:0 0 13px;width:13px;height:13px;position:relative;
    cursor:help;color:var(--orange);align-items:center;justify-content:center}
  .campo .exige.on{display:inline-flex}
  .campo .exige:hover .dica{display:block}
  .campo .exige::after{content:"";width:7px;height:7px;border-radius:50%;
                       background:currentColor}
  .campo .exige .dica{left:auto;right:20px;width:300px}

  .guarda{flex:1;min-height:0;display:flex;flex-direction:column;
          overflow-y:auto;overflow-x:auto;
          margin-top:7px;padding-top:7px;border-top:1px solid var(--linha)}
  .guarda::-webkit-scrollbar{width:10px}
  .guarda::-webkit-scrollbar-track{background:transparent}
  .guarda::-webkit-scrollbar-thumb{background:var(--border-forte);border-radius:5px}
  .guarda::-webkit-scrollbar-thumb:hover{background:var(--comment)}
  .guarda table{height:100%}
  .tab.miuda thead th{padding:5px 8px;background-color:var(--panel);border-bottom:1px solid var(--linha)}

  .tab thead th:nth-child(1){background-image:linear-gradient(color-mix(in srgb, var(--cyan) 14%, transparent),color-mix(in srgb, var(--cyan) 14%, transparent))}
  .tab thead th:nth-child(2){background-image:linear-gradient(color-mix(in srgb, var(--purple) 20%, transparent),color-mix(in srgb, var(--purple) 20%, transparent))}
  .tab thead th:nth-child(3){background-image:linear-gradient(color-mix(in srgb, var(--orange) 14%, transparent),color-mix(in srgb, var(--orange) 14%, transparent))}
  .tab.miuda td{padding:1px 8px;cursor:default}
  .gd-nome{vertical-align:middle;white-space:nowrap;font-size:11px}
  .tab.miuda{min-width:524px}
  .gd-pecas{width:271px}
  .gd-pecas .gls{gap:5px}
  .gc{position:relative;display:inline-flex}
  .gq{display:inline-flex;align-items:center;gap:2px;border-radius:3px}
  .gq.nd{outline:1px dashed var(--comment);outline-offset:1px}
  .gp{position:absolute;left:50%;bottom:-6px;width:4px;height:4px;margin-left:-2px;
      border-radius:50%;background:var(--fg);visibility:hidden}
  .gp.on{visibility:visible}
  .gr{display:inline-flex;align-items:center;gap:2px;color:var(--fg)}
  .gr.on{color:var(--purple);filter:drop-shadow(0 0 4px rgba(189,147,249,.45))}
  .gr .gl{vertical-align:-3px}
  .gd-id{width:118px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:10px;
         color:var(--fg)}
  .tab.miuda td:first-child{position:relative}
  .gd-nome .pl{position:absolute;left:0;top:0;bottom:0;width:3px;
               background:currentColor;color:transparent}
  .tab.miuda tr.fora .gd-nome{color:var(--fg)}
  .tab.miuda tr.fora .gr,.tab.miuda tr.fora .gp{visibility:hidden}

  .barra-quatro{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:14px 0 2px}
  .barra-quatro .btn{width:100%;height:36px;justify-content:center;font-size:12.5px}
  .barra-quatro .btn.verde,.barra-quatro .btn.verde:hover{background:var(--green);
      color:var(--app-bg);border-color:var(--green);font-weight:700}
  .barra-quatro .btn.verde.apagado,.barra-quatro .btn.verde.apagado:hover{background:transparent;
      color:var(--fg);border-color:var(--border-sutil);font-weight:inherit;cursor:not-allowed}
  .perfis > div{padding:12px 16px}
  .perfis > div:first-child{padding-right:8px}
  .perfis > div:last-child{padding-left:8px}
  .rolo .tab tbody td{height:26px;padding-top:0;padding-bottom:0}
  .rolo .tab thead th[data-coluna]{cursor:pointer;user-select:none}
  .quadro-titulo[data-dica],.cab[data-dica]{cursor:help}
  .tab col[data-coluna="criado"],.tab col[data-coluna="modificado"]{width:104px}
  .tab td .renome{width:100%;box-sizing:border-box;height:22px;font:inherit;padding:0 6px;
                  border:1px solid var(--purple);border-radius:5px;background:var(--app-bg);color:var(--fg)}
  .tab td.data{font-family:'JetBrains Mono',monospace;color:var(--fg);font-weight:400;
               white-space:nowrap}
  .tab th.data{white-space:nowrap}
  .campos{gap:4px}
  .campo .seg.alvos{flex-wrap:nowrap;gap:6px;flex:1;min-width:0}
  .campo .seg.alvos button{flex:1 1 0;min-width:0;height:var(--h-escolha);padding:0 8px}
  .campo.so-eventos{display:none}
  .campo.so-eventos.on{display:grid}
  .ev-val{display:flex;gap:10px;align-items:center;min-width:0}
  .campo.so-comando{display:none}
  .campo.so-eventos.on:has(option[value="meu_comando"]:checked) + .campo.so-comando{display:grid}
  .campo select.estreito{flex:1 1 auto;width:100%}
  .ordem-vale{margin:4px 0 8px;display:none}
  .ordem-vale.on{display:block}
  .ordem-vale .cab{font-size:11.5px;font-weight:700;color:var(--fg);margin:0 0 4px}
  .ordem-vale ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
  .ordem-vale li{display:flex;align-items:center;gap:8px;height:28px;padding:0 10px;font-size:12px;
                 border:1px solid var(--linha);border-radius:7px;background:var(--app-bg);
                 color:var(--fg);cursor:grab}
  .ordem-vale li.ativo{border-color:var(--purple)}
  .ordem-vale li.arrastando-este{opacity:.45}
  .ordem-vale .pos{flex:0 0 18px;font-family:'JetBrains Mono',monospace;color:var(--fg);
                   text-align:right}
  .ordem-vale .pega{color:var(--fg);letter-spacing:-2px}
  .guarda table{table-layout:fixed;width:100%;min-width:0 !important}
  .guarda col[data-coluna="controle"]{width:136px}
  .guarda col[data-coluna="id"]{width:114px}
  .guarda td.gd-id,.guarda th.gd-id{font-size:10px;letter-spacing:-.2px;padding-left:6px;
                                    padding-right:6px}
  @media (max-width:1259px){
    .guarda col[data-coluna="id"],.guarda th.gd-id,.guarda td.gd-id{display:none}
  }
  @media (max-height:860px){
    .campo{height:32px}
    .campo input,.campo select,.campo .seg button{height:32px !important;min-height:0}
    .ordem-vale li{height:26px}
    .ordem-vale{margin:0 0 6px}
  }
  @media (max-height:780px){
    .campos{padding:8px 12px}
    .campo{height:28px;margin-bottom:3px}
    .campo input,.campo select,.campo .seg button{height:28px !important}
    .ordem-vale li{height:24px}
    .ordem-vale ol{gap:3px}
    .ordem-vale .cab{margin-bottom:3px}
    .tab.miuda thead th{padding:3px 8px}
  }
"""

CABEM_NA_TIRA = 413

CADEADO = ('<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
           '<path d="M3.6 5.2V3.9a2.4 2.4 0 0 1 4.8 0v1.3" fill="none" '
           'stroke="currentColor" stroke-width="1.2"/>'
           '<rect x="2.3" y="5.2" width="7.4" height="5.4" rx="1.1" '
           'fill="currentColor"/></svg>')


LUPA = ('<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
        '<circle cx="5.2" cy="5.2" r="3.4" fill="none" stroke="currentColor" '
        'stroke-width="1.3"/>'
        '<path d="M7.8 7.8 L10.6 10.6" stroke="currentColor" stroke-width="1.3" '
        'stroke-linecap="round"/></svg>')

RECARREGA = ('<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
             '<path d="M9.8 6a3.8 3.8 0 1 1-1.2-2.8" fill="none" '
             'stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
             '<path d="M9.4 1.3v2.6H6.8" fill="none" stroke="currentColor" '
             'stroke-width="1.3" stroke-linecap="round" '
             'stroke-linejoin="round"/></svg>')


def icone_do_rotulo(gesto: str, desenho: str, dica: str, aria: str = "") -> str:
    """Um ícone clicável no título de um bloco; a dica é `data-dica`, o `aria` é a frase longa."""
    return (f'<button type="button" class="icone-rot" '
            f'data-hef-gesto="{gesto}" data-dica="{dica}" '
            f'aria-label="{aria or dica}">{desenho}</button>')


def icone_da_lupa() -> str:
    """A lupa do título da tabela dos perfis. Ela ABRE o campo, e nada mais."""
    return ('<button type="button" class="icone-rot lupa" '
            'data-dica="Procura pelo nome ou pelo jogo" '
            f'aria-label="Procurar um perfil">{LUPA}</button>')


def campo_da_lupa() -> str:
    """O campo que a lupa abre — fechado no desenho, e é decisão de produto."""
    return ('<input type="text" class="procura" data-hef="perfis.procura" '
            'data-hef-alvo="valor" data-hef-vivo="procurar" '
            'placeholder="procurar" aria-label="Procurar um perfil" value="">')


def puxador(coluna: str, tabela: str) -> str:
    """A divisa arrastável no canto direito de um `<th>`."""
    return (f'<span class="puxador" data-hef-gesto="largura-da-coluna" '
            f'data-tabela="{tabela}" data-coluna="{coluna}" data-px="0" '
            f'role="separator" aria-label="Arraste para mudar a largura da coluna"></span>')


def cabeca(coluna: str, rotulo_visivel: str, tabela: str, classe: str = "",
           divisa: bool = True, dica: str = "Duplo clique ordena") -> str:
    """Um `<th>` da lista de perfis: o nome, a seta da ordem e a divisa."""
    cls = f' class="{classe}"' if classe else ""
    return (f'<th{cls} data-coluna="{coluna}" data-dica="{dica}">'
            f'{rotulo_visivel}'
            f'<span class="ordena" data-hef="perfis.ordem.{coluna}" '
            f'data-hef-alvo="atributo" data-hef-atributo="data-ordem" '
            f'data-hef-gesto="ordenar" data-coluna="{coluna}"></span>'
            f'{puxador(coluna, tabela) if divisa else ""}</th>')


def marca_com_dica(classe: str, campo_estado: str, campo_frase: str,
                   miolo: str = "") -> str:
    """O cadeado (ou o ponto) que só aparece quando o produto tem o que dizer."""
    return (f'<span class="{classe}" data-hef="{campo_estado}"'
            f' data-hef-alvo="classe">{miolo}'
            f'<span class="dica" data-hef="{campo_frase}"'
            f' data-hef-alvo="html"></span></span>')


ESTILOS = [e.rotulo for e in ESTILOS_DO_MOTOR]
PERFIS = [("Mortal Kombat", 90, "Steam · Mortal Kombat 1 · 1971870", True),
          ("Mortal Kombat online", 88, "Steam · Mortal Kombat 1 · 1971870", False),
          ("Elden Ring", 85, "Steam · Elden Ring · 1245620", False),
          ("Orpheus", 82, "RetroArch · Orpheus: To Hell and Back", False),
          ("Pragmata", 80, "Steam · Pragmata · 1358160", False),
          ("Don't Scream", 78, "Steam · Don't Scream · 2380050", False),
          ("Reanimal", 76, "Heroic · Reanimal", False),
          ("Faith", 74, "Instalado aqui · faith.exe", False),
          ("Wendigo Blue", 72, "Lutris · Wendigo Blue", False),
          ("Duskfade", 70, "Heroic · Duskfade", False),
          ("Mina the Hollower", 68, "Instalado aqui · mina.exe", False),
          ("Terror (os dez)", 60, "Só neste programa", False),
          ("Luta", 58, "Só neste programa", False),
          ("Navegação", 40, ROTULO_SO_QUANDO_ESCOLHER, False),
          ("Universal", 0, ROTULO_SO_QUANDO_ESCOLHER, False)]

PROCEDENCIA_DO_DESENHO = PERFIS[0][2].split(SEPARADOR_DA_PROCEDENCIA)[0]

SEM_DATA = ("—", "—")
DATAS_DO_DESENHO = {
    "Mortal Kombat": ("03/09/2026", "11/10/2026"),
    "Mortal Kombat online": ("10/10/2026", "10/10/2026"),
    "Elden Ring": ("21/08/2026", "02/10/2026"),
    "Orpheus": ("14/09/2026", "14/09/2026"),
    "Pragmata": ("18/09/2026", "07/10/2026"),
    "Faith": ("26/09/2026", "01/10/2026"),
    "Duskfade": ("30/09/2026", "30/09/2026"),
    "Mina the Hollower": ("02/10/2026", "09/10/2026"),
}
ORDEM_DO_DESENHO = ["Mortal Kombat", "Mortal Kombat online"]

ALVOS_DO_DESENHO = [
    ("jogos", "Jogos", "Vale quando o jogo abre"),
    ("navegacao", "Navegação", "Vale fora do jogo, no computador"),
    ("programas", "Programas", "Vale com o programa na frente"),
    ("eventos", "Eventos", "Um momento do jogo, do sistema ou o seu comando"),
]
MOMENTOS_DO_DESENHO = [
    ("No jogo", [("cena", "Cena"), ("menu", "Menu"), ("pausa", "Pausa")]),
    ("No sistema", [("controle_conectado", "Controle conectado"),
                    ("programa_aberto", "Programa aberto"), ("hora_marcada", "Hora marcada")]),
    ("Meu", [("meu_comando", "Meu comando")]),
]
DICAS_DOS_ESTILOS = {"Nativo": "O jogo decide"}

PRI_DO_DESENHO = PERFIS[0][1]
PERFIL_DO_EDITOR = PERFIS[0][0]
PCT_DO_DESENHO = round(PRI_DO_DESENHO * 100 / PRIORIDADE_MAXIMA)

TRAVESSAO = "—"


def opts(lista, escolhido, vazio=False, travessao=False):
    """As opções de um `<select>` do desenho."""
    linhas = []
    if vazio:
        linhas.append('                <option value="" disabled selected>—</option>')
    if travessao:
        linhas.append(f'                <option value="{TRAVESSAO}" disabled>'
                      f'{TRAVESSAO}</option>')
    linhas += [f'                <option{" selected" if (o == escolhido and not vazio) else ""}'
               f'{f" data-dica={chr(34)}{DICAS_DOS_ESTILOS[o]}{chr(34)}" if o in DICAS_DOS_ESTILOS else ""}>{o}</option>'
               for o in lista]
    return "\n".join(linhas)


from pacotes.a11_calibrar_sensores import bloco_de_nascenca as _mira_de_nascenca  # noqa: E402
from pacotes.a11_calibrar_sensores import resumo_da_mira as _resumo_da_mira  # noqa: E402

_RESUMO_DA_MIRA_NA_CENA = _resumo_da_mira(_mira_de_nascenca()) or ""


def _celula_de_agora(c, campo, agora):
    """`(aceso, não_diz, dica)` de uma célula do cenário `AGORA`.

    A máscara é a da `MESA` (`c["mascara"]`), com a regra do pacote
    (`a10_perfis._mascara_agora`): acesa só na DualSense.
    """
    if campo == "mascara" and campo not in agora:
        mascara = str(c.get("mascara") or "")
        if mascara in ("", NAO_DIZ):
            return False, True, DICA_DO_NAO_DIZ
        if mascara != MASCARA_QUE_ACENDE:
            return False, False, DICA_DA_MASCARA.format(mascara=mascara)
        return True, False, ""
    valor = agora.get(campo, "sim")
    if valor == NAO_DIZ:
        return False, True, DICA_DO_NAO_DIZ
    return valor == "sim", False, (_RESUMO_DA_MIRA_NA_CENA
                             if campo == "movimento" and c.get("conectado", True) else "")


def linha_do_controle(c, tem=None, id_da_peca=None, uniq=None, agora=None):
    """Uma linha da tabela de baixo: o controle, o que é só dele, e o ID da peça."""
    na_mesa = c.get("conectado", True)
    tem = GUARDA[c["pref"]] if tem is None else tem
    agora = AGORA.get(c["pref"], {}) if agora is None else agora
    id_visivel = ID_DA_PECA[c["pref"]] if id_da_peca is None else id_da_peca
    endereco = uniq if uniq is not None else c["pref"]
    grupos = []
    for campo, pecas in SECOES:
        on, nao_diz, dica_da_celula = _celula_de_agora(c, campo, agora)
        gs = "".join(glifo(p, ativo=on, tam=15) for p in pecas)
        titulo = f' data-dica="{dica_da_celula}"' if dica_da_celula else ""
        grupos.append(
            f'<span class="gc" data-hef="guarda.dica" data-hef-alvo="atributo"'
            f' data-hef-atributo="data-dica"{titulo}>'
            f'<span class="gr{" on" if on else ""}" data-hef="guarda.secao"'
            f' data-hef-alvo="classe" data-hef-secao="{campo}">'
            f'<span class="gq{" nd" if nao_diz else ""}" data-hef="guarda.incerto"'
            f' data-hef-alvo="classe" data-hef-classe="nd">{gs}</span></span>'
            f'<span class="gp{" on" if campo in tem else ""}" data-hef="guarda.proprio"'
            f' data-hef-alvo="classe"></span></span>')
    nome = SEPARADOR.join([c["nome"], c["via"]]) if na_mesa else c["nome"]
    plastico = cor_da_zona(c['cor'])
    dica = ("" if na_mesa else
            '\n                      data-dica="Quando ele voltar, encontra o que você deixou"')
    return f'''                  <tr data-hef-uniq="{endereco}" data-hef="guarda.vazio" data-hef-alvo="classe" data-hef-classe="fora"{'' if na_mesa else ' class="fora"'}{dica}>
                    <td class="gd-nome">
                      <span class="pl" data-hef="guarda.plastico" data-hef-alvo="cor"
                            style="color:{plastico}"></span>
                      <span data-hef="guarda.nome">{nome}</span>
                    </td>
                    <td class="gd-pecas"><span class="gls">{"".join(grupos)}</span></td>
                    <td class="gd-id" data-hef="guarda.id">{id_visivel}</td>
                  </tr>'''


def linha_do_perfil(nome, criado, modificado, ativo, dica="", escolhido=False):
    """Uma linha da lista de perfis salvos, a MESMA para o mockup e para a viva.

    O dono da forma é este gerador; a linha viva (`a10_perfis._linha_da_lista`) a repete e uma
    régua compara as duas caractere a caractere. O clique em QUALQUER célula sobe até a `<tr>`
    (`data-hef-gesto="selecionar"`), que ativa o perfil e o abre no editor. O nome viaja no
    `data-hef-perfil`, não no texto. `escolhido` é a linha aberta no editor e sai sempre em
    `aria-selected` (`true` ou `false`), para o `<tbody>` assentar a cada tique. O parâmetro
    `dica` fica por compatibilidade: a dica da linha é fixa e nasce em `data-dica`.
    """
    return (f'                <tr tabindex="0" data-dica="Clique: ativa e abre no editor" '
            f'class="{"ativo" if ativo else ""}" '
            f'data-hef-perfil="{nome}" data-hef-gesto="selecionar" '
            f'aria-selected="{"true" if escolhido else "false"}">'
            f'<td data-hef="perfis.linha.nome" data-dica="Clique abre no editor; duplo clique renomeia">{nome}</td>'
            f'<td class="data" data-hef="perfis.linha.criado">{criado}</td>'
            f'<td class="data" data-hef="perfis.linha.modificado">{modificado}</td></tr>')


def botao_do_alvo(valor, rotulo_visivel, dica):
    """Um dos quatro botões de «Aplicar em»; só o do jogo nasce aceso (a classe `on`)."""
    ligado = ' class="on"' if valor == "jogos" else ""
    return (f'                  <button{ligado} '
            f'data-hef="editor.alvo.{valor}" data-hef-alvo="classe" data-hef-classe="on" '
            f'data-hef-gesto="editor.alvo" data-v="{valor}" data-dica="{dica}">'
            f'{rotulo_visivel}</button>')


def opcoes_do_quando():
    """O `<select>` de «Quando»: o travessão (sem momento) e os sete momentos, em três grupos."""
    grupos = [f'                  <option value="{TRAVESSAO}" disabled selected>{TRAVESSAO}</option>']
    for nome_do_grupo, itens in MOMENTOS_DO_DESENHO:
        grupos.append(f'                  <optgroup label="{nome_do_grupo}">'
                      + "".join(f'<option value="{v}">{r}</option>' for v, r in itens)
                      + "</optgroup>")
    return "\n".join(grupos)


def item_da_ordem(nome, posicao, ativo):
    """Um `<li>` de «Qual vale primeiro»: o mesmo que `a10_perfis._html_da_ordem` escreve."""
    return (f'                  <li class="{"ativo" if ativo else ""}" draggable="true" tabindex="0" '
            f'data-hef-gesto="editor.ordem" data-hef-perfil="{nome}">'
            f'<span class="pos">{posicao}</span><span class="pega">⋮⋮</span>{nome}</li>')



CAMPO_DA_RAZAO_DO_ATIVAR = "perfis.ativar-razao"
DICA_DO_ATIVAR = "Passa a usar este perfil agora"
ATIVAR = botao_cinza("Ativar", CAMPO_DA_RAZAO_DO_ATIVAR, tom="verde",
                     extra=f'data-hef-gesto="ativar" title="{DICA_DO_ATIVAR}"')


def servico_parado(html):
    """A cena do serviço parado, derivada do desenho normal: o que o produto escreve.

    O topo leva `data-servico="parado"` (some a contagem, D-2010-O-SERVICO-PARADO-NAO-GANHA-FRASE) e
    o nome do perfil fica no travessão, que é o «nada está valendo» do topo; nenhuma linha da lista
    nem da ordem fica verde de VALENDO. O Ativar segue verde e clicável: um clique religa o serviço e
    troca o perfil, e o clique na linha faz o mesmo. Sem frase nova na tela.
    """
    trocas = (
        ('data-servico="de-pe"', 'data-servico="parado"'),
        ('<tr tabindex="0" data-dica="Clique: ativa e abre no editor" class="ativo" ',
         '<tr tabindex="0" data-dica="Clique: ativa e abre no editor" class="" '),
        ('<li class="ativo" draggable="true"', '<li class="" draggable="true"'),
    )
    for velho, novo in trocas:
        if velho not in html:
            raise SystemExit(f"ERRO na cena do serviço parado: {velho[:60]!r} sumiu do desenho")
        html = html.replace(velho, novo)
    return re.sub(r'(<span class="pa-nome"[^>]*>)[^<]*(</span>)', r"\1—\2", html)


ROTEIRO = """
  <script>
  (function(){
    'use strict';
    var PISO = 48, TETO = 900;

    function oCampo(){ return document.querySelector('.procura'); }
    document.addEventListener('click', function(ev){
      var b = ev.target.closest ? ev.target.closest('.icone-rot.lupa') : null;
      if(!b) return;
      var campo = oCampo();
      if(!campo) return;
      var abrindo = !campo.classList.contains('on');
      campo.classList.toggle('on', abrindo);
      b.classList.toggle('on', abrindo);
      if(abrindo){ campo.focus(); return; }
      if(campo.value !== ''){
        campo.value = '';
        campo.dispatchEvent(new Event('input', {bubbles: true}));
      }
    }, false);

    document.addEventListener('dblclick', function(ev){
      var nome = ev.target.closest ? ev.target.closest('td[data-hef="perfis.linha.nome"]') : null;
      if(nome){ renomear(nome); return; }
      var th = ev.target.closest ? ev.target.closest('th[data-coluna]') : null;
      if(!th) return;
      var seta = th.querySelector('.ordena[data-hef-gesto]');
      if(seta) seta.click();
    }, false);

    function renomear(td){
      if(td.querySelector('input')) return;
      var tr = td.closest('tr[data-hef-perfil]');
      if(!tr) return;
      var era = tr.dataset.hefPerfil;
      var guarda = document.createElement('span');
      guarda.hidden = true;
      guarda.textContent = td.textContent;
      var campo = document.createElement('input');
      campo.type = 'text';
      campo.className = 'renome';
      campo.value = era;
      campo.setAttribute('aria-label', 'Novo nome do perfil');
      campo.dataset.hefGesto = 'perfis.renomear';
      campo.dataset.hefPerfil = era;
      td.textContent = '';
      td.appendChild(guarda);
      td.appendChild(campo);
      campo.focus();
      campo.select();
      campo.addEventListener('keydown', function(e){
        e.stopPropagation();
        if(e.key === 'Enter'){ e.preventDefault(); campo.blur(); }
        else if(e.key === 'Escape'){ e.preventDefault(); campo.value = era; campo.blur(); }
      });
      campo.addEventListener('blur', function(){
        setTimeout(function(){ if(td.contains(campo)) td.textContent = guarda.textContent; }, 0);
      });
    }

    var voo = null;
    function colDe(pux){
      var tab = pux.closest('table');
      var col = tab ? tab.querySelector('col[data-coluna="' + pux.dataset.coluna + '"]') : null;
      return {tabela: tab, col: col};
    }

    function caber(th, col, px){
      col.style.width = px + 'px';
      for(var i = 0; th && i < 8; i++){
        var falta = th.scrollWidth - th.clientWidth;
        if(falta <= 0) break;
        px = px + falta;
        col.style.width = px + 'px';
      }
      return px;
    }
    function ajustar(tab){
      tab.querySelectorAll('th[data-coluna]').forEach(function(th){
        var col = tab.querySelector('col[data-coluna="' + th.dataset.coluna + '"]');
        if(!col || th.clientWidth >= th.scrollWidth) return;
        var px = caber(th, col, Math.round(th.getBoundingClientRect().width));
        var pux = th.querySelector('.puxador');
        if(pux) pux.dataset.px = String(px);
      });
    }
    document.addEventListener('mousedown', function(ev){
      var pux = ev.target.closest ? ev.target.closest('.puxador') : null;
      if(!pux) return;
      var alvo = colDe(pux);
      if(!alvo.col) return;
      var th = pux.closest('th');
      voo = {pux: pux, col: alvo.col, th: th, x: ev.clientX,
             largura: th ? th.getBoundingClientRect().width : 0};
      document.body.classList.add('arrastando');
      ev.preventDefault();
    }, false);
    document.addEventListener('mousemove', function(ev){
      if(!voo) return;
      var px = Math.round(voo.largura + (ev.clientX - voo.x));
      if(px < PISO) px = PISO;
      if(px > TETO) px = TETO;
      px = caber(voo.th, voo.col, px);
      voo.pux.dataset.px = String(px);
    }, false);
    document.addEventListener('mouseup', function(){
      if(!voo) return;
      var pux = voo.pux;
      voo = null;
      document.body.classList.remove('arrastando');
      pux.click();
    }, false);
    document.addEventListener('keydown', function(ev){
      if(ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight') return;
      var pux = ev.target.closest ? ev.target.closest('.puxador') : null;
      if(!pux) return;
      var alvo = colDe(pux);
      var th = pux.closest('th');
      if(!alvo.col || !th) return;
      var px = Math.round(th.getBoundingClientRect().width) + (ev.key === 'ArrowRight' ? 8 : -8);
      px = caber(th, alvo.col, Math.max(PISO, Math.min(TETO, px)));
      pux.dataset.px = String(px);
      ev.preventDefault();
      pux.click();
    }, false);

    function espalhar(tab){
      var bruto = tab.getAttribute('data-larguras') || '';
      if(!bruto || bruto === '\\u2014') return;
      bruto.split('\\u00b7').forEach(function(par){
        var pedaco = par.split(':');
        if(pedaco.length !== 2) return;
        var px = parseInt(pedaco[1], 10);
        if(!isFinite(px)) return;
        if(px < PISO) px = PISO;
        if(px > TETO) px = TETO;
        var col = tab.querySelector('col[data-coluna="' + pedaco[0] + '"]');
        var th = tab.querySelector('th[data-coluna="' + pedaco[0] + '"]');
        if(col) px = caber(th, col, px);
        var pux = tab.querySelector('.puxador[data-coluna="' + pedaco[0] + '"]');
        if(pux) pux.dataset.px = String(px);
      });
    }
    function medir(tab){
      tab.querySelectorAll('.puxador').forEach(function(pux){
        var th = pux.closest('th');
        if(!th) return;
        var px = Math.round(th.getBoundingClientRect().width);
        if(px > 0 && (pux.dataset.px || '0') === '0') pux.dataset.px = String(px);
      });
    }
    function tabelas(){ return document.querySelectorAll('table[data-tabela]'); }
    function assentar(){ tabelas().forEach(function(t){ espalhar(t); medir(t); ajustar(t); }); }
    tabelas().forEach(function(t){
      new MutationObserver(function(){ espalhar(t); }).observe(
        t, {attributes: true, attributeFilter: ['data-larguras']});
      var cabeca = t.querySelector('thead');
      if(cabeca) new MutationObserver(function(){ ajustar(t); }).observe(
        cabeca, {attributes: true, subtree: true, attributeFilter: ['data-ordem']});
    });
    document.addEventListener('click', function(ev){
      var b = ev.target.closest ? ev.target.closest('.seg.alvos button') : null;
      if(!b) return;
      b.parentNode.querySelectorAll('button').forEach(function(o){
        o.classList.toggle('on', o === b);
      });
      var quando = document.querySelector('.so-eventos');
      if(quando) quando.classList.toggle('on', b.dataset.v === 'eventos');
      var ordem = document.querySelector('.ordem-vale');
      if(ordem) ordem.classList.toggle('on', b.dataset.v !== 'eventos');
    }, false);

    var puxado = null;
    document.addEventListener('dragstart', function(ev){
      var li = ev.target.closest ? ev.target.closest('.ordem-vale li') : null;
      if(!li) return;
      puxado = li;
      li.classList.add('arrastando-este');
      if(ev.dataTransfer){
        ev.dataTransfer.effectAllowed = 'move';
        try { ev.dataTransfer.setData('text/plain', li.getAttribute('data-hef-perfil') || ''); }
        catch(e) { }
      }
    }, false);
    document.addEventListener('dragover', function(ev){
      if(!puxado) return;
      var alvo = ev.target.closest ? ev.target.closest('.ordem-vale li') : null;
      if(!alvo || alvo === puxado || alvo.parentNode !== puxado.parentNode) return;
      ev.preventDefault();
      var r = alvo.getBoundingClientRect();
      alvo.parentNode.insertBefore(puxado, ev.clientY < r.top + r.height / 2 ? alvo : alvo.nextSibling);
    }, false);
    document.addEventListener('dragend', function(){
      if(!puxado) return;
      var li = puxado;
      puxado = null;
      li.classList.remove('arrastando-este');
      var itens = Array.prototype.slice.call(li.parentNode.children);
      itens.forEach(function(x, i){
        var pos = x.querySelector('.pos');
        if(pos) pos.textContent = String(i + 1);
      });
      li.dataset.posNova = String(itens.indexOf(li) + 1);
      li.click();
    }, false);

    if(document.readyState === 'loading'){
      document.addEventListener('DOMContentLoaded', assentar);
    } else { assentar(); }
  })();
  </script>
"""


MIOLO = f'''
    <div class="quadro estica">
      <div class="quadro-topo">
        <span class="quadro-titulo" data-dica="Um perfil guarda tudo que você ajustou nas abas">Perfis</span>
      </div>
      <div class="desfecho" data-hef="perfis.desfecho" data-hef-alvo="classe"><span data-hef="perfis.desfecho"></span></div>
      <div class="quadro-corpo">
        <div class="perfis">

          <div>
            <div class="moldura">
              <div class="sec-rot">Perfis salvos{icone_da_lupa()}{campo_da_lupa()}{icone_do_rotulo(
                  "recarregar", RECARREGA, "Relê a lista",
                  "Relê a lista de perfis. Não mexe no editor ao lado.")}<span class="fora-da-busca" data-hef="perfis.procura.conta" data-hef-alvo="classe"><span data-hef="perfis.procura.conta"></span></span></div>
              <div class="lista">
              <div class="rolo">
              <table class="tab" data-hef="perfis.larguras" data-hef-alvo="atributo"
                     data-hef-atributo="data-larguras" data-tabela="10-perfis.lista"
                     data-larguras="">
                <colgroup><col data-coluna="nome"><col data-coluna="criado"><col data-coluna="modificado"></colgroup>
                <thead><tr>{cabeca("nome", "Nome", "10-perfis.lista", dica="Duplo clique ordena")}{cabeca(
                    "criado", "Criado em", "10-perfis.lista", classe="data", dica="Quando o perfil nasceu")}{cabeca(
                    "modificado", "Modificado em", "10-perfis.lista", classe="data",
                    divisa=False, dica="A última vez que você salvou")}</tr></thead>
                <tbody data-hef="perfis.lista">
{chr(10).join(linha_do_perfil(n, *DATAS_DO_DESENHO.get(n, SEM_DATA), a, escolhido=n == PERFIL_DO_EDITOR) for n,_p,_q,a in PERFIS)}
                </tbody>
              </table>
              </div>
              </div>
            </div>
          </div>

          <div>
            <div class="moldura">
              <div class="sec-rot">Editar</div>
              <div class="campos">

              <div class="campo">
                <span>Nome do jogo:</span>
                <span class="val">
                  <input type="text" data-hef="editor.jogo" data-hef-gesto="editor.jogo"
                         data-hef-alvo="valor" list="jogos-desta-maquina"
                         data-dica="Escolha um jogo desta máquina; o perfil leva o nome dele"
                         value="Mortal Kombat 1">{marca_com_dica(
                           "exige", "editor.jogo.exige", "editor.jogo.exigencia")}
                  <datalist id="jogos-desta-maquina" data-hef="editor.jogo.lista"></datalist>
                </span>
              </div>
              <div class="campo">
                <span>Aplicar em:</span>
                <span class="val"><span class="seg alvos">
{chr(10).join(botao_do_alvo(v, r, d) for v, r, d in ALVOS_DO_DESENHO)}
                </span></span>
              </div>
              <div class="campo so-eventos" data-hef="editor.alvo.eventos" data-hef-alvo="classe">
                <span data-dica="Quando o perfil entra">Quando:</span>
                <span class="val ev-val"><select class="estreito" data-hef="editor.evento" data-hef-gesto="editor.quando" data-hef-alvo="valor" aria-label="Quando o perfil entra">
{opcoes_do_quando()}
                </select></span>
              </div>
              <div class="campo so-comando">
                <span data-dica="O perfil entra quando o comando termina sem erro">Comando:</span>
                <span class="val"><input type="text" class="ev-cmd" data-hef="editor.evento.comando" data-hef-gesto="editor.quando" data-que="comando" data-hef-alvo="valor" aria-label="Comando ou arquivo .sh" placeholder="Comando ou arquivo .sh"
                  data-dica="Um comando de terminal ou um arquivo .sh" value=""></span>
              </div>
              <div class="campo">
                <span data-dica="O estilo decide o automático: gatilho, vibração e luz">Estilo de jogo:</span>
                <span class="val"><select class="destaque estreito" data-hef="editor.estilo" data-hef-gesto="editor.estilo" data-hef-alvo="valor">
{opts(ESTILOS, "", vazio=True)}
                </select></span>
              </div>
              <div class="ordem-vale on" data-hef="editor.ordem.ha" data-hef-alvo="classe" data-hef-classe="on">
                <div class="cab" data-dica="Arraste: o de cima vale quando os dois servem">Qual vale primeiro</div>
                <ol data-hef="editor.ordem">
{chr(10).join(item_da_ordem(n, i, n == PERFIL_DO_EDITOR) for i, n in enumerate(ORDEM_DO_DESENHO, 1))}
                </ol>
              </div>
              <div class="guarda">
                <table class="tab miuda" data-hef="guarda.larguras" data-hef-alvo="atributo"
                       data-hef-atributo="data-larguras" data-tabela="10-perfis.guarda"
                       data-larguras="">
                  <colgroup><col data-coluna="controle"><col data-coluna="status"><col data-coluna="id"></colgroup>
                  <thead><tr>
                    <th data-dica="Um ajuste por controle, guardado no perfil">Controle{puxador("controle", "10-perfis.guarda")}</th>
                    <th class="gd-pecas" data-dica="{DICA_DO_STATUS}">Status{puxador("status", "10-perfis.guarda")}</th>
                    <th class="gd-id" data-dica="Por este endereço o perfil reconhece o controle">ID da peça</th>
                  </tr></thead>
                  <tbody data-hef="guarda.linhas">
{chr(10).join(linha_do_controle(c) for c in MESA)}
                  </tbody>
                </table>
              </div>

              </div>
            </div>
          </div>

        </div>
        <div class="barra-quatro-onde"><div class="barra-quatro">
          <button class="btn" data-hef-gesto="duplicar" data-dica="Copia o perfil, com «(cópia)» no nome">Duplicar</button>
          <button class="btn" data-hef-gesto="novo" data-dica="Perfil em branco; com jogo aberto, nasce para ele">Novo</button>
          <button class="btn vermelho" data-hef-gesto="remover" data-hef="perfis.remover" data-dica="Apaga o perfil; pergunta antes">Remover</button>
          {ATIVAR}
        </div></div>
      </div>
    </div>
{ROTEIRO}
'''

LEGENDA = '''<div class="nota">
  <h2>O que mudou na Perfis do todo (15/10/2026)</h2>
  <ul>
    <li><b>A lista conta quando o perfil nasceu e quando você o mudou.</b> Colunas
      <b>Nome</b>, <b>Criado em</b> e <b>Modificado em</b>; perfil de antes das datas mostra
      <b>—</b>. O duplo clique no cabeçalho ordena (datas: o mais novo primeiro; o <b>—</b> fica
      sempre embaixo). Um clique na linha <b>ativa e abre</b> o perfil, e o <b>Perfil ativo</b>
      do topo e o editor mostram o mesmo nome.</li>
    <li><b>O editor procura o perfil pelo nome do jogo.</b> <b>Nome do jogo</b> (a lista é a dos jogos
      desta máquina), <b>Aplicar em</b> (Jogos, Navegação, Programas, Eventos) e, só em
      Eventos, o <b>Quando</b> (um momento do jogo, do sistema ou o seu comando). Saíram o
      Nome, a Preferência (o controle deslizante), o Funciona em e o Detectar.</li>
    <li><b>Qual vale primeiro.</b> Com dois perfis do mesmo jogo, arrastar um acima do outro
      decide qual entra quando os dois servem. O perfil que o Hefesto criou sozinho cede a vez
      ao seu.</li>
    <li><b>O estilo ganhou três.</b> <b>Nativo</b> (o jogo decide: gatilho, vibração e luz em
      Automático), <b>Visual novel</b> e <b>Adulto</b>; o <b>Point and click</b> trouxe a tabela
      de botões do jogo de clicar. O seletor abre em <b>—</b>.</li>
    <li><b>Quatro botões embaixo</b>, do mesmo tamanho: Duplicar, Novo, Remover e Ativar (verde).
      O botão largo sozinho saiu.</li>
    <li><b>A tabela por controle fala pela cor do plástico</b> (<b>Galactic Purple</b>, <b>White</b>),
      também nos lugares vazios, e as dicas viram <code>data-dica</code>.</li>
  </ul>

  <h2>O que você mandou tirar, e continua fora</h2>
  <ul>
    <li><b>"◆ 2 perfis nunca vão entrar — veja quais"</b>, com o <b>?</b> — fora.</li>
    <li><b>"Salvar este perfil"</b> — fora.</li>
    <li><b>"Esconder os controles físicos neste jogo"</b> — fora.</li>
    <li><b>"◆ este jogo já sabe por onde entra"</b> — fora: <span class="marca">isso está na aba Jogar</span>, palavra sua.</li>
    <li><b>O quadro "Modo"</b>, com os quatro botões — fora: <span class="marca">isso está na aba Jogar</span>, palavra sua.
      O que este perfil já guarda continua guardado — nenhum botão desta aba mexe nisso.
      <span class="marca">Quem escreve o modo é a Jogar, e ela escreve no perfil que está valendo</span>.</li>
  </ul>

  <h2>O que estava no código e nunca teve tela</h2>
  <ul>
    <li><b>Os ajustes por controle</b> — <code>Profile.controllers</code> existe desde
      16/07 e gravava calado: nenhuma tela dizia quais controles têm ajuste próprio.
      Era a pergunta <b>4</b> do contrato desta aba, e a tabela é a resposta.</li>
    <li><b>"Voltar à de ontem"</b> — cada gravação já guarda a anterior e nenhuma tela oferecia isso (<code>profiles/loader.py:1864</code>).</li>
  </ul>

  <h2>Ainda é sua a palavra</h2>
  <ul>
    <li><b>"O jogo vê o controle como" não está desenhado aqui.</b> Ele mora hoje na
      <b>Jogar</b>; se vem também para cá, é decisão sua, e a tela não decide por você.
      <span class="marca">O "Modo que liga" saiu desta lista</span> — você já decidiu, e
      ele está no bloco de cima.</li>
    <li><b>O conteúdo dos estilos de jogo</b> continua em aberto: a lista está aqui, o que
      cada um liga não.</li>
    <li><b>A tabela é leitura</b>, como a fita esmaecida diz. Se você quiser mudar o ajuste de
      um controle a partir daqui — em vez de ir à aba da peça com aquele controle escolhido
      na fita —, isso é tela nova, e eu não a inventei.</li>
  </ul>
</div>

</body>
</html>
'''

def _conferir(html: str) -> None:
    """Lê o HTML que acabou de sair e reprova se uma decisão de produto cair."""
    falhas = []

    def exigir(cond, queixa):
        if not cond:
            falhas.append(queixa)

    regra = re.search(r"\.campo > span:first-child\{[^}]*\}", html)
    exigir(regra is not None, "a regra do rótulo do campo sumiu do CSS")
    if regra:
        exigir("text-align:left" in regra.group(0),
               "o rótulo do campo não alinha mais à esquerda")
        exigir("text-align:right" not in regra.group(0),
               "o rótulo do campo voltou a alinhar à direita")
        exigir("white-space:nowrap" in regra.group(0),
               "o `nowrap` saiu — um rótulo que crescer vira duas linhas e estoura a altura")

        exigir("var(--fg)" in regra.group(0),
               "o rótulo do campo voltou ao verde — o verde é de ESTADO, não de nome")
        exigir("font-weight:700" in regra.group(0),
               "o negrito do rótulo saiu — sem ele o nome vira dado")

    r = re.search(r"\.tab thead th\{[^}]*\}", html)
    exigir(r is not None, "a regra dos cabeçalhos de coluna sumiu do CSS")
    if r:
        exigir("color:var(--fg)" in r.group(0),
               "os cabeçalhos de coluna voltaram ao verde — verde é de ESTADO, não de nome")
        exigir("font-weight:700" in r.group(0),
               "o negrito dos cabeçalhos saiu — sem ele o nome vira dado")

    r = re.search(r"\.sec-rot\{[^}]*\}", html)
    exigir(r is not None, "a regra do título de bloco sumiu do CSS")
    if r:
        exigir("color:var(--rot-campo)" in r.group(0),
               "o título de bloco perdeu o verde que ela pediu")
    for titulo in ("Perfis salvos", "Editar"):
        exigir(f'class="sec-rot">{titulo}<' in html,
               f"o título de bloco '{titulo}' não está na tela")

    for rot in ("Nome do jogo:", "Aplicar em:", "Quando:", "Estilo de jogo:"):
        exigir(f">{rot}</span>" in html, f"o rótulo '{rot}' não está na tela")
    for velho in ("Nome:", "Preferência:", "Funciona em:"):
        exigir(f">{velho}</span>" not in html,
               f"o rótulo '{velho}' voltou — o editor da Perfis do todo não o tem")
    for coluna, rot in (("nome", "Nome"), ("criado", "Criado em"), ("modificado", "Modificado em")):
        th = re.search(rf'<th[^>]*data-coluna="{coluna}"[^>]*>{rot}<', html)
        exigir(th is not None, f"o cabeçalho '{rot}' sumiu da lista de perfis")
    exigir('data-coluna="prioridade"' not in html and 'data-coluna="quando"' not in html,
           "a lista voltou às colunas Preferência e Funciona em — a Perfis do todo mostra "
           "Nome, Criado em e Modificado em")

    fundos = re.findall(r"\.tab thead th:nth-child\(\d\)\{background-image:([^}]*)\}", html)
    exigir(len(fundos) == 3, f"não são 3 fundos de coluna no CSS, e sim {len(fundos)}")
    exigir(len(set(fundos)) == 3, "os fundos das três colunas não são cores diferentes")

    fora = [c for c in MESA if not c.get("conectado", True)]
    exigir("Desconectado</span>" not in html,
           "voltou o «Desconectado» ao lugar vazio — ele fala pela cor do plástico (sem P3)")
    for c in MESA:
        esperado = (SEPARADOR.join([c["nome"], c["via"]]) if c.get("conectado", True)
                    else c["nome"])
        exigir(f'<span data-hef="guarda.nome">{esperado}</span>' in html,
               f"o nome do lugar de {c['nome']} não é «{esperado}»")
        exigir(rotulo(c, "curta") not in html,
               f"o rótulo de mesa «Pn • …» de {c['nome']} continua na tela — a cor do plástico "
               f"fala no lugar do número do jogador")
    exigir(html.count('class="fora"') == len(fora),
           "os lugares desconectados perderam a classe que os apaga")

    exigir(html.count('data-hef="guarda.plastico"') == len(MESA),
           f"não são {len(MESA)} barras com endereço `guarda.plastico` na tabela por controle")
    exigir(html.count('data-hef-alvo="cor"') == len(MESA),
           "a barra do plástico perdeu o alvo `cor` — o `fundo` soma uma pintura por tique")
    exigir("--plastico:" not in html.split('class="miolo"')[-1],
           "voltou um `--plastico` cravado no miolo — identidade de aparelho sem endereço")

    linhas = re.findall(r"<tr data-hef-uniq=\"[^\"]+\"[^>]*>", html)
    exigir(len(linhas) == len(MESA),
           f"não são {len(MESA)} linhas na tabela por controle, e sim {len(linhas)}")
    na_mesa_com_dica = [t for c, t in zip(MESA, linhas, strict=True)
                        if c.get("conectado", True) and "data-dica=" in t]
    exigir(not na_mesa_com_dica,
           f"{len(na_mesa_com_dica)} linha(s) de controle NA MESA voltaram a ter "
           f"dica — ela congela o nome do modelo do desenho por cima de um "
           f"aparelho que é outro")
    fora_sem_dica = [c["pref"] for c, t in zip(MESA, linhas, strict=True)
                     if not c.get("conectado", True) and "data-dica=" not in t]
    exigir(not fora_sem_dica,
           f"o lugar vazio {fora_sem_dica} perdeu a dica que explica por que ele "
           f"continua na tabela — ela não fala de aparelho nenhum")

    blocos_por_lugar = {
        m.group(1): re.findall(r'data-(?:campo|papel|hef)="([^"]+)"', m.group(0))
        for m in re.finditer(r'<tr data-hef-uniq="(p\d)".*?</tr>', html, re.S)
    }
    exigir(len(blocos_por_lugar) == len(MESA),
           f"não são {len(MESA)} lugares endereçados na tabela por controle, "
           f"e sim {len(blocos_por_lugar)}")
    if len(blocos_por_lugar) == len(MESA):
        assinaturas = {pref: tuple(sorted(collections.Counter(campos).items()))
                       for pref, campos in blocos_por_lugar.items()}
        modelo = assinaturas[MESA[0]["pref"]]
        divergentes = sorted(p for p, a in assinaturas.items() if a != modelo)
        exigir(not divergentes,
               f"os lugares {divergentes} não têm os MESMOS endereços do "
               f"{MESA[0]['pref']} — um lugar com endereço a menos come a carga "
               f"dela em silêncio, e um com contagem diferente desloca as "
               f"células de `guarda.secao` de todos os lugares seguintes. "
               f"Endereços por lugar: "
               f"{ {p: sum(c for _k, c in a) for p, a in assinaturas.items()} }")

    exigir(".campos > .campo::after" not in html,
           "as linhas horizontais voltaram ao editor de perfil")

    celulas = re.findall(r'<span class="gr[^"]*" data-hef="guarda\.secao"[^>]*>', html)
    exigir(len(celulas) == len(MESA) * len(SECOES),
           f"não são {len(MESA) * len(SECOES)} células de `guarda.secao` "
           f"({len(MESA)} controles x {len(SECOES)} seções), e sim {len(celulas)}")
    com_dica = [c for c in celulas if "data-dica=" in c]
    exigir(not com_dica,
           f"{len(com_dica)} célula(s) de `Ajuste próprio` voltaram a ter dica — "
           f'ela mandou as oito saírem: "Auto falante é auto falante, gatilho é gatilho"')

    for endereco in ("guarda.dica", "guarda.incerto", "guarda.proprio"):
        quantas = html.count(f'data-hef="{endereco}"')
        exigir(quantas == len(MESA) * len(SECOES),
               f"não são {len(MESA) * len(SECOES)} células de `{endereco}`, e sim "
               f"{quantas}")
    dicas_das_celulas = re.findall(
        r'<span class="gc" data-hef="guarda\.dica"[^>]*?data-dica="([^"]*)"', html)
    estranhas = [d for d in dicas_das_celulas
                 if d not in (DICA_DO_NAO_DIZ, _RESUMO_DA_MIRA_NA_CENA)
                 and not re.fullmatch(re.escape(DICA_DA_MASCARA).replace(
                     re.escape("{mascara}"), ".+"), d)]
    exigir(not estranhas,
           f"a célula da coluna «Status» ganhou uma dica que o pacote não "
           f"escreve: {estranhas}")

    sem_alvo = [c for c in celulas if 'data-hef-alvo="classe"' not in c]
    exigir(not sem_alvo,
           f"{len(sem_alvo)} célula(s) de `guarda.secao` sem "
           f'`data-hef-alvo="classe"` — pintá-las apagaria o glifo')

    exigir('data-hef-secao="mic"' in html,
           "a coluna do microfone sumiu da linha `Ajuste próprio` (decisão nº20)")
    sem_nome = [campo for campo, _ in SECOES if campo not in NOME_DA_SECAO]
    exigir(not sem_nome,
           f"a(s) seção(ões) {sem_nome} não têm nome em `NOME_DA_SECAO` — a dica "
           f"do cabeçalho não saberia como chamá-la na tela")

    exigir(html.count('data-hef="perfis.desfecho"') == 2,
           "a tira do desfecho perdeu um dos dois endereços — sem o `classe` "
           "ela fica acesa com um travessão; sem o `<span>` ela nunca escreve")
    exigir('class="desfecho" data-hef="perfis.desfecho" data-hef-alvo="classe"' in html,
           "a tira do desfecho perdeu o alvo `classe` — ela acenderia sempre")
    exigir("visibility:hidden" in html,
           "a tira do desfecho perdeu o `visibility:hidden` — ela apareceria "
           "vazia em toda tela sem recado")

    regra = re.search(r"\.desfecho\{[^}]*\}", html)
    exigir(regra is not None, "a regra da tira do desfecho sumiu do CSS")
    acesa = re.search(r"\.desfecho\.on\{[^}]*\}", html)
    exigir(acesa is not None, "a regra `.desfecho.on` sumiu do CSS")
    if regra and acesa:
        corpo = regra.group(0)
        exigir("height:0" in corpo and "margin-top:0" in corpo,
               "a tira do desfecho voltou a reservar espaço em REPOUSO — são "
               "37px de banda morta debaixo do título, e ela os chamou de "
               "bizarros em 05/09")
        exigir("height:30px" in acesa.group(0),
               "a tira do desfecho voltou a UMA linha — o fim da frase, que é "
               "a metade que avisa, some com reticências")
        exigir("margin-top:7px" in acesa.group(0),
               "a tira acesa perdeu a folga de 7px que a separa do título")
        exigir("-webkit-line-clamp:2" in corpo,
               "a tira perdeu o `-webkit-line-clamp:2` — a frase longa vaza "
               "para fora da caixa em vez de parar na segunda linha")
        exigir("white-space:nowrap" not in corpo,
               "o `nowrap` voltou à tira — com ele a frase continua numa linha "
               "só, e as duas linhas reservadas viram espaço morto")

    for classe, estado, frase in (
            ("exige", "editor.jogo.exige", "editor.jogo.exigencia"),):
        marca = re.search(rf'<span class="{classe}"[^>]*>', html)
        exigir(marca is not None,
               f"a marca `{classe}` sumiu do editor — o campo volta a ficar "
               f"idêntico a um destravado e só reclama depois do clique")
        if marca:
            exigir(f'data-hef="{estado}"' in marca.group(0)
                   and 'data-hef-alvo="classe"' in marca.group(0),
                   f"a marca `{classe}` perdeu o endereço que a acende "
                   f"(`{estado}`, alvo `classe`) — ela ficaria escondida para "
                   f"sempre, ou visível para sempre")
        exigir(f'<span class="dica" data-hef="{frase}" data-hef-alvo="html">'
               f'</span>' in html,
               f"a dica de `{classe}` não é um `{frase}` VAZIO no desenho — ou "
               f"o endereço sumiu, ou o mockup passou a cravar uma frase que é "
               f"dado do perfil dela")

    exigir('data-hef="editor.jogo.rotulo"' not in html and "gesto=\"detectar\"" not in html,
           "o rótulo do jogo ou o Detectar voltou ao editor — o campo «Nome do jogo» é o único "
           "caminho, e o perfil leva o nome do jogo escolhido")
    exigir("grid-template-columns:var(--rot-p) minmax(0,1fr)" in html,
           "a fileira do campo voltou a `1fr` — uma pista de grade cresce com o "
           "MIN-CONTENT e estoura a página")

    exigir('<div class="campo modo">' not in html,
           "o quadro Modo voltou ao editor de Perfis — ele sai por ordem dela "
           "de 11/09/2026, e a aba onde o modo se escolhe é a Jogar")
    exigir('data-modo="' not in html,
           "um botão desta aba voltou a carregar `data-modo` — o atributo é do "
           "quadro que saiu; se for outro controle reusando o nome, ele precisa "
           "de nome próprio, porque a régua de ponteiros da casa o lê como modo")
    exigir('data-hef="editor.modo"' not in html,
           "o endereço `editor.modo` voltou à página — o gesto que o gravava "
           "saiu de `a10_perfis` junto com o quadro, e um endereço sem gesto é "
           "um botão que responde calado")
    exigir(".campo.modo" not in html,
           "a regra `.campo.modo` voltou ao CSS — ela reservava a altura solta "
           "da fileira de quatro botões, e era essa fileira (36px) que deixava "
           "a linha do P4 fora do quadro sempre que a tira do desfecho acendia")

    exigir("O quadro &quot;Modo&quot;" in LEGENDA or 'O quadro "Modo"' in LEGENDA,
           "a legenda (nota de revisão, fora da página) parou de dizer que o quadro Modo saiu e onde ele mora — "
           "quem abrir a aba depois de 11/09 procuraria um quadro que a versão "
           "anterior tinha, sem nada na tela que o mande à Jogar")

    exigir("no perfil que está valendo" in LEGENDA,
           "a legenda perdeu o ALCANCE do que a aba Jogar escreve — sem ele a "
           "frase promete que a Jogar escolhe o modo de QUALQUER perfil, e o "
           "escritor (`Daemon.gravar_o_modo_escolhido`) só alcança o perfil "
           "ativo")
    exigir("quem o escolhe é a Jogar" not in LEGENDA,
           "a frase larga voltou à legenda — ela afirma que a Jogar escolhe o "
           "modo de qualquer perfil, e a Jogar grava só no que está valendo")

    regra_nome = re.search(r"\.gd-nome\{[^}]*\}", html)
    exigir(regra_nome is not None, "a regra `.gd-nome` sumiu do CSS")
    if regra_nome:
        exigir("display:flex" not in regra_nome.group(0),
               "o `<td>` do nome voltou a `display:flex` — ele deixa de ser "
               "célula de tabela e o nome desalinha do glifo e do ID em 8px, "
               "que é a linha «quebrada» que ela fotografou")
        exigir("vertical-align:middle" in regra_nome.group(0),
               "o `<td>` do nome perdeu o `vertical-align:middle` — sem ele o "
               "texto pousa no topo da linha e as três colunas deixam de "
               "alinhar assim que a linha ganha altura")

    exigir('<datalist id="jogos-desta-maquina" data-hef="editor.jogo.lista">'
           '</datalist>' in html,
           "a lista dos jogos desta máquina sumiu, ou deixou de nascer VAZIA — "
           "um exemplo cravado aqui é a tela afirmando um jogo que ela talvez "
           "não tenha")
    campo_do_jogo = re.search(r'<input[^>]*data-hef="editor\.jogo"[^>]*>', html)
    exigir(campo_do_jogo is not None, "o campo do jogo sumiu do editor")
    if campo_do_jogo:
        exigir('list="jogos-desta-maquina"' in campo_do_jogo.group(0),
               "o campo do jogo perdeu o `list=` — a lista continua no HTML e "
               "nenhum campo a consulta, que é o silêncio que esta casa lê "
               "como sucesso")

    exigir("editor.prioridade" not in html and 'class="trilho"' not in html,
           "a Preferência (o slider) voltou à tela — a ordem entre perfis do mesmo jogo agora se "
           "arrasta em «Qual vale primeiro»")
    exigir("editor.ambiente" not in html and "editor.nome\"" not in html,
           "o «Funciona em» ou o «Nome:» voltou à tela — «Aplicar em» e «Nome do jogo» os "
           "substituem")

    for e in ESTILOS_DO_MOTOR:
        exigir(f">{e.rotulo}</option>" in html,
               f"o estilo '{e.rotulo}' está no motor e não está no `<select>` "
               f"— o gesto saberia aplicá-lo e ela não teria como pedir")
    exigir('<option value="" disabled selected>—</option>' in html,
           "a opção vazia do estilo de jogo saiu — o campo voltaria a abrir "
           "afirmando um estilo que perfil nenhum guarda")
    exigir('data-dica="O estilo decide o automático: gatilho, vibração e luz">Estilo de jogo:' in html,
           "a dica do estilo de jogo mudou — ela é a frase curta do desenho")
    opcoes = re.search(r'<select class="destaque estreito"[^>]*>(.*?)</select>', html, re.S)
    exigir(opcoes is not None, "o select do estilo sumiu")
    if opcoes:
        rotulos = re.findall(r">([^<]+)</option>", opcoes.group(1))
        exigir(rotulos[:2] == ["—", "Nativo"] and rotulos[-1] == "Personalizado",
               f"o estilo abre em «—», depois «Nativo», e fecha em «Personalizado»: {rotulos}")
        exigir('<option data-dica="O jogo decide">Nativo</option>' in opcoes.group(1),
               "o Nativo perdeu a dica «O jogo decide»")
    exigir("Criar perfil de point and click" not in html and "Criar perfil de point-and-click"
           not in html,
           "voltou o botão «Criar perfil de point and click» — o estilo Point and click do "
           "select já faz o perfil")
    exigir("um-so" not in html and 'class="botoes' not in html,
           "voltou o botão largo sozinho (`.um-so`) — o Ativar fica na barra de quatro")
    exigir(not re.search(r'\bclass="[^"]*\bajuda\b', html),
           "voltou o «?» do título da Perfis — a dica agora mora no próprio título")

    barra = re.search(r'<div class="barra-quatro">(.*?)</div></div>', html, re.S)
    exigir(barra is not None, "a barra dos quatro botões sumiu")
    if barra:
        gestos = re.findall(r'data-hef-gesto="([^"]+)"', barra.group(1))
        exigir(gestos == ["duplicar", "novo", "remover", "ativar"],
               f"a barra de baixo não é Duplicar, Novo, Remover, Ativar: {gestos}")
    alvos = re.findall(r'data-hef-gesto="editor\.alvo" data-v="([^"]+)"', html)
    exigir(alvos == ["jogos", "navegacao", "programas", "eventos"],
           f"«Aplicar em» não tem os quatro lugares na ordem: {alvos}")
    exigir('class="campo so-eventos"' in html and 'hidden' not in
           re.search(r'<div class="campo so-eventos"[^>]*>', html).group(0),
           "o «Quando» perdeu a classe `so-eventos` ou ganhou `hidden` (quem esconde é o CSS)")
    exigir('data-hef="editor.ordem"' in html and 'class="ordem-vale on"' in html,
           "o bloco «Qual vale primeiro» sumiu")
    exigir(".ordem-vale.on{display:block}" in html and 'data-hef="editor.ordem.ha"' in html,
           "«Qual vale primeiro» deixou de sumir com menos de dois perfis no jogo")

    exigir("--rot-p:86px" in html,
           "a coluna do rótulo não é mais a medida do rótulo mais largo (86px)")
    exigir("--rot-p:104px" not in html,
           "a coluna do rótulo voltou aos 104px — 22px de vão morto por rótulo")


    exigir('class="icone-rot lupa"' in html,
           "a lupa sumiu do título da tabela dos perfis — ela é ordem dela de "
           "11/09/2026 e é por onde o campo de busca aparece")
    exigir('data-papel="abrir-a-lupa"' not in html,
           "a lupa voltou a endereçar por `data-papel` — o ouvinte do piloto "
           "casa esse atributo, e cada clique nela chegaria ao Python como um "
           "gesto SEM DONO, imprimindo no stdout de quem lançou a janela")
    campo = re.search(r'<input[^>]*class="procura"[^>]*>', html)
    exigir(campo is not None, "o campo da lupa sumiu da página")
    if campo:
        exigir('data-hef-vivo="procurar"' in campo.group(0),
               "o campo da lupa perdeu o `data-hef-vivo` — sem a quarta porta "
               "do piloto, digitar nele não manda nada a lugar nenhum: as três "
               "outras portas despacham no clique, no `change` e no `blur`")
        exigir('data-hef-alvo="valor"' in campo.group(0),
               "o campo da lupa perdeu o alvo `valor` — a pintura escreveria o "
               "termo como TEXTO dentro de um `<input>`, que não aparece")
        exigir('value=""' in campo.group(0),
               "o campo da lupa nasce com termo dentro — o desenho passaria a "
               "afirmar uma busca que ela não fez")
    exigir('class="procura on"' not in html,
           "o campo da lupa nasce ABERTO — um campo de busca sempre visível "
           "acrescenta uma linha ao bloco em vez de tirar, e a ordem dela era "
           "de limpeza")

    regra_seta = re.search(r"\.ordena\{[^}]*\}", html)
    exigir(regra_seta is not None, "a regra da seta da ordem sumiu do CSS")
    if regra_seta:
        exigir("pointer-events:none" in regra_seta.group(0),
               "a seta da ordem perdeu o `pointer-events:none` — ela carrega o "
               "gesto `ordenar`, e sem esta linha um clique "
               "SIMPLES no cabeçalho passa a ordenar. Ela pediu DUPLO clique, "
               "e a razão está na regra: o cabeçalho é `sticky` a um pixel da "
               "célula que troca o perfil aberto no editor")
    for coluna in ("nome", "criado", "modificado"):
        seta = re.search(rf'<span class="ordena" data-hef="perfis\.ordem\.{coluna}"[^>]*>',
                         html)
        exigir(seta is not None,
               f"a coluna `{coluna}` não tem seta de ordem — ela é o que diz "
               f"qual coluna ordena e para onde, sem texto novo")
        if seta:
            exigir('data-hef-gesto="ordenar"' in seta.group(0)
                   and f'data-coluna="{coluna}"' in seta.group(0),
                   f"a seta da coluna `{coluna}` perdeu o gesto ou o nome da "
                   f"coluna — o duplo clique chegaria ao Python sem dizer por "
                   f"qual coluna ordenar")
            exigir('data-hef-alvo="atributo"' in seta.group(0)
                   and 'data-hef-atributo="data-ordem"' in seta.group(0),
                   f"a seta da coluna `{coluna}` mudou de alvo — só o "
                   f"`atributo` chega à tela nos TRÊS estados: ele é o único "
                   f"que APAGA quando o valor é vazio. Com `classe` a seta "
                   f"fica vazia e invisível; com `texto`, as colunas não "
                   f"ordenadas ganham um «—»")

    regra_base = re.search(r"\.ordena\{[^}]*\}", html)
    exigir(regra_base is not None and "margin-left" not in regra_base.group(0),
           "a regra `.ordena` voltou a ter margem incondicional — um span vazio "
           "com margem empurra o rótulo e abrevia o cabeçalho na tela, com a "
           "palavra inteira no HTML. A margem mora em `.ordena[data-ordem]`")
    exigir(re.search(r"\.ordena\[data-ordem\]\{[^}]*margin-left", html) is not None,
           "a seta ORDENADA perdeu a margem — ela encosta no rótulo da coluna")
    exigir('.tab col[data-coluna="criado"],.tab col[data-coluna="modificado"]{width:104px}' in html,
           "as colunas de data perderam a largura que cabe «dd/mm/aaaa» com a seta da ordem")

    for seta_glifo in ("↑", "↓"):
        exigir(f'.ordena[data-ordem="{seta_glifo}"]::after{{content:"{seta_glifo}"}}' in html,
               f"o glifo `{seta_glifo}` sumiu do CSS — quem desenha a seta é o "
               f"`content`, porque o piloto não escreve texto no alvo "
               f"`atributo`. Sem esta regra a seta some da tela e nada diz "
               f"qual coluna ordena")

    for gesto_, canto, dica_ in (
            ("recarregar", "Perfis salvos", "Relê a lista"),):
        icone = re.search(rf'<button type="button" class="icone-rot" '
                          rf'data-hef-gesto="{gesto_}"[^>]*>', html)
        exigir(icone is not None,
               f"o gesto `{gesto_}` não é um ícone do rótulo — ele virou ícone "
               f"por ordem dela em 11/09/2026, e o nome do gesto não muda por "
               f"troca de invólucro")
        if icone:
            exigir(f'data-dica="{dica_}"' in icone.group(0),
                   f"o ícone de `{gesto_}` perdeu a dica, palavra por palavra. "
                   f"Um ícone sem dica é uma função que ninguém acha — é o "
                   f"custo inteiro de trocar palavra por desenho")
        bloco = html.split(f'class="sec-rot">{canto}')
        exigir(len(bloco) == 2 and f'data-hef-gesto="{gesto_}"' in bloco[1][:700],
               f"o ícone de `{gesto_}` não está no rótulo `{canto}` — ela disse "
               f"onde cada um vai, e são cantos diferentes de propósito")
    exigir(html.count('class="btn" data-hef-gesto="voltar-a-de-ontem"') == 0
           and html.count('class="btn" data-hef-gesto="recarregar"') == 0,
           "um dos dois voltou a ser botão na fileira do rodapé — a fileira de "
           "TRÊS virou UM, e é isso que faz o layout ficar mais limpo sem "
           "acrescentar altura nenhuma")
    exigir('data-hef-gesto="voltar-a-de-ontem"' not in html,
           "o `voltar-a-de-ontem` voltou à tela — a ordem dela de 11/09 foi "
           "removê-lo, e o ícone dele ao lado de «Editar» era lido como o "
           "recarregar duplicado")
    regra_icone = re.search(r"\.icone-rot\{[^}]*\}", html)
    exigir(regra_icone is not None, "a regra do ícone do rótulo sumiu do CSS")
    if regra_icone:
        exigir("width:24px" in regra_icone.group(0)
               and "height:24px" in regra_icone.group(0),
               "o ícone do rótulo perdeu o alvo de 24x24 — o desenho tem 11px, "
               "e 11px é o DESENHO, não a área clicável")

    th_status = re.search(r'<th class="gd-pecas"[^>]*>([^<]*)', html)
    exigir(th_status is not None, "o cabeçalho da coluna do meio sumiu")
    if th_status:
        exigir(th_status.group(1).strip() == "Status",
               f"o rótulo da coluna não é `Status`: {th_status.group(1)!r}. "
               f"Ela mandou trocar o nome em 11/09/2026, e SÓ o nome")
    exigir("controles com ajuste próprio" not in html,
           "o contador «controles com ajuste próprio» voltou ao título — a Perfis do todo não o tem")
    exigir(DICA_DO_STATUS in html,
           "a dica do `<th>` não diz as duas camadas — ela é quem explica o que "
           "o glifo aceso e o ponto embaixo querem dizer, e encurtar o rótulo só "
           "funciona porque a explicação tem outro dono")
    exigir("guarda um ajuste só deste controle" not in html,
           "a frase do significado de antes voltou à página — a coluna pinta o "
           "controle agora, e o disco é o ponto")

    regra_tab = re.search(r"\.tab\{[^}]*\}", html)
    exigir(regra_tab is not None, "a regra da tabela sumiu do CSS")
    exigir("table-layout:fixed" in html,
           "a tabela voltou a `table-layout:auto` — nele a `width` é SUGESTÃO, "
           "e a largura que ela arrastar é reescrita pelo navegador no próximo "
           "repinte. Está medido neste arquivo desde 31/08: `.tab .pri` dizia "
           "46px e o Chrome media 86px")  # (noqa-acento)
    exigir(html.count('<col data-coluna=') == 6,
           "não são 6 `<col>` nas duas tabelas — o `<colgroup>` é quem carrega "
           "a largura, e é o único elemento da tabela que o `blocos` do piloto "
           "não reescreve")
    puxadores = re.findall(r'<span class="puxador"[^>]*>', html)
    exigir(len(puxadores) == 4,
           f"não são 4 divisas arrastáveis, e sim {len(puxadores)} — duas por "
           f"tabela, porque a última coluna não tem o que redistribuir")
    for pux in puxadores:
        exigir('data-hef-gesto="largura-da-coluna"' in pux
               and 'data-tabela="' in pux and 'data-px="' in pux,
               "uma divisa perdeu o gesto, a tabela ou o número — soltar o "
               "arraste deixaria de gravar, e a coluna voltaria ao que era na "
               "próxima abertura")
    regra_pux = re.search(r"\.puxador\{[^}]*\}", html)
    exigir(regra_pux is not None, "a regra da divisa sumiu do CSS")
    if regra_pux:
        exigir("cursor:col-resize" in regra_pux.group(0),
               "a divisa perdeu o `cursor:col-resize` — «quando o cursor muda "
               "e permite alterar a largura da coluna» é a descrição dela do "
               "gesto, e sem o cursor não há gesto a achar")

    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import roteiros_de

    roteiro = next((corpo for atributos, corpo in roteiros_de(html) if not atributos), None)
    exigir(roteiro is not None,
           "o roteiro da página sumiu — sem ele a lupa não abre, o duplo "
           "clique não ordena e a divisa não arrasta")
    if roteiro is not None:
        corpo = roteiro
        for peca, queixa in (
                ("icone-rot.lupa", "o roteiro parou de abrir o campo da lupa"),
                ("dblclick", "o roteiro parou de ouvir o DUPLO clique — e um "
                             "clique simples no cabeçalho é vizinho de um "
                             "gesto que troca o perfil aberto no editor"),
                ("classList.add('arrastando')", "o roteiro perdeu o arraste da divisa"),
                ("MutationObserver", "o roteiro parou de vigiar o "
                                     "`data-larguras` — a largura que volta do "
                                     "disco chega por ali, e só por ali")):
            exigir(peca in corpo, queixa)

    if falhas:
        raise SystemExit("ERRO em 10-perfis — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


if __name__ == "__main__":
    import os
    import pathlib
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-10-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = monta("10-perfis", "Perfis", MIOLO, CSS)
    _conferir(onde.pagina("10-perfis.html").read_text(encoding="utf-8"))
    if len(sys.argv) == 3 and sys.argv[1] == "--servico-parado":
        _cena = pathlib.Path(sys.argv[2])
        _cena.mkdir(parents=True, exist_ok=True)
        (_cena / "10-perfis.html").write_text(
            servico_parado((_prova / "10-perfis.html").read_text(encoding="utf-8")),
            encoding="utf-8")
    else:
        shutil.copyfile(_prova / "10-perfis.html", _real / "10-perfis.html")
    shutil.rmtree(_prova)
    ROT_P = re.search(r"--rot-p:(\d+)px", CSS).group(1)
    FORA = sum(1 for c in MESA if not c.get("conectado", True))
    print(f"10-perfis: OK, {n} divs · rótulo à esquerda com dois pontos, coluna de {ROT_P}px, "
          f"zero divisórias no editor · Perfis salvos e Editar · {FORA} lugar(es) vazio(s)")
