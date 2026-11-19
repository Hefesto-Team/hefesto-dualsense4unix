"""O mapa das atualizações, as versões anteriores e o andamento.

O mapa nasce do botão «Atualizações» da aba Sistema (e sozinho, quando o prazo vence com peça
nova): uma linha por peça, com o nome, a versão de agora → a nova, o estado por glifo e cor e a
marca; o «Atualizar tudo» e as versões anteriores no rodapé. O andamento usa a mesma linha, com a
barra da peça em curso. A explicação mora na dica. A caixa nasce por cima de qualquer aba
(``JS_DA_CAIXA``) e se repinta inteira a cada mudança. Puro: recebe os dicionários do motor e
devolve HTML.
"""
from __future__ import annotations

import html
import json
import re
import time
from collections.abc import Sequence
from typing import Any

ID_DA_CAIXA = "hef-atualizacoes"
ORDEM_NA_TELA = ("hefesto", "proton", "bluetooth", "som", "portal", "gdk", "python", "nvidia",
                 "kernel", "dkms", "sistema", "mangohud", "umu")
ESTADOS_DO_MAPA = ("nova", "revisar", "em_dia")
GRUPO_DO_ESTADO = {"fixa": "em_dia"}
REINSTALAVEIS = ("em_dia", "revisar")
ROTULO_DO_ATUALIZAR = "Atualizar tudo"
DICA_DA_REINSTALACAO = "Marcar reinstala a versão de agora"
DICA_SEM_REINSTALAR = "O Hefesto ainda não reinstala esta peça"
DICA_SEM_REDE = "Sem rede: a versão publicada não foi conferida"
DICA_DO_SOZINHO = "Sem pergunta, só com o jogo fechado"
DICA_DO_PRAZO = "Prazo da conferência"
DICA_DO_REGISTRO = "O registro desta atualização"
DICA_DO_JOGO = "Espera o jogo fechar"
DICA_DA_FILA = "Espera a atualização em curso"
PARADA, PARANDO, REINICIE = "Parada", "Parando…", "Reinicie o computador para concluir"
GLIFO_DA_REINSTALACAO = "↻"
ATUALIZADO, NOVA_VERSAO, ESPERANDO, APLICANDO, FALHOU, NA_FILA, A_REVISAR, SEM_REDE = (
    "Atualizado", "Nova versão", "Esperando", "Aplicando", "Falhou", "Na fila", "A revisar",
    "Sem rede")
GLIFO = {"ok": "✓", "nova": "↑", "esperando": "◷", "aplicando": "●", "falhou": "!",
         "fila": "○", "revisar": "!", "sem-rede": "?"}
ESTADO_DO_MAPA = {"nova": ("nova", NOVA_VERSAO), "em_dia": ("ok", ATUALIZADO),
                  "revisar": ("revisar", A_REVISAR), "sem_rede": ("sem-rede", SEM_REDE)}
ESTADO_DO_ANDAMENTO = {"fila": ("fila", NA_FILA), "baixando": ("aplicando", APLICANDO),
                       "instalando": ("aplicando", APLICANDO),
                       "aplicando": ("aplicando", APLICANDO),
                       "reiniciando": ("aplicando", APLICANDO),
                       "esperando": ("esperando", ESPERANDO),
                       "pronta": ("ok", ATUALIZADO), "atualizada": ("ok", ATUALIZADO),
                       "falhou": ("falhou", FALHOU)}
ETAPA_NA_DICA = {"baixar": "Baixar", "instalar": "Instalar", "aplicar": "Aplicar em todos",
                 "reiniciar": "Reiniciar o serviço", "reabrir": "Reabrir o Hefesto"}
ICONES = {
    "hefesto": '<path d="M3 7h13l5-3v5l-5 2v2h-3v3h3l1 4H6l1-4h3v-3H7v-1.5C5 11 3 9.5 3 7z"/>',
    "proton": '<circle cx="12" cy="12" r="9"/><path d="M10 8.5v7l6-3.5z"/>',
    "bluetooth": '<path d="M7 7l10 10-5 5V2l5 5L7 17"/>',
    "som": '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 9a4 4 0 0 1 0 6"/>'
           '<path d="M19 6.5a7.5 7.5 0 0 1 0 11"/>',
    "portal": '<path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4"/><circle cx="12" cy="12" r="3"/>',
    "gdk": '<path d="M7 8h10a5 5 0 0 1 5 5v1a3 3 0 0 1-5.4 1.8L15 14H9l-1.6 1.8A3 3 0 0 1 2 14'
           'v-1a5 5 0 0 1 5-5z"/><path d="M7 11v3M5.5 12.5h3"/><circle cx="16.5" cy="12" r=".6"/>',
    "python": '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M13.5 5l-3 14"/>',
    "nvidia": '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="9" cy="12" r="3"/>'
              '<path d="M15 10h3.5M15 14h3.5"/>',
    "kernel": '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 7V3M14 7V3M10 21v-4'
              'M14 21v-4M7 10H3M7 14H3M21 10h-4M21 14h-4"/>',
    "dkms": '<rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" '
            'height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/>'
            '<path d="M17 14v6M14 17h6"/>',
    "sistema": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>',
    "mangohud": '<path d="M3.5 17a8.5 8.5 0 1 1 17 0"/><path d="M12 17l4.5-5"/>'
                '<path d="M3 20h18"/>',
    "umu": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M10 9v6l5-3z"/>',
    "": '<rect x="4" y="4" width="16" height="16" rx="2"/>',
}

CSS = """
.hef-atualiza{display:none;position:fixed;inset:0;z-index:70;background:rgba(9,10,15,.72);
  align-items:center;justify-content:center;font-family:'Space Grotesk',system-ui,sans-serif}
.hef-atualiza.aberta{display:flex}
body:has(.hef-atualiza.aberta) :not(.hef-atualiza,.hef-atualiza *){scrollbar-width:none}
.hef-atualiza .tn-cx{width:660px;max-width:94vw;background:var(--panel);border-radius:11px;
  border:1px solid var(--border-forte);box-shadow:0 26px 70px rgba(0,0,0,.62);display:flex;
  flex-direction:column;max-height:min(717px,calc(100vh - 40px))}
.hef-atualiza .tn-topo{display:flex;align-items:center;gap:9px;padding:14px 18px 0;flex:none}
.hef-atualiza .tn-tit{font-size:14.5px;font-weight:600;color:var(--purple)}
.hef-atualiza .tn-x{margin-left:auto;width:26px;height:26px;border-radius:6px;cursor:pointer;
  border:1px solid var(--border-forte);color:var(--fg);font-size:14px;background:transparent;
  display:flex;align-items:center;justify-content:center}
.hef-atualiza .tn-x:hover{border-color:var(--red);color:var(--red)}
.hef-atualiza .tn-corpo{padding:11px 18px 14px;display:flex;flex-direction:column;gap:10px;
  min-height:0;overflow-y:auto}
.hef-atualiza .tn-rod{display:flex;align-items:center;gap:10px;padding:12px 18px 16px;flex:none;
  border-top:1px solid var(--border-sutil)}
.hef-atualiza .tn-rod .empurra{margin-left:auto}
.hef-atualiza .btn{height:var(--h-acao,34px);padding:0 13px;border-radius:7px;font-size:12.5px;
  font-family:inherit;cursor:pointer;border:1px solid var(--linha,#53576f);background:transparent;
  color:var(--texto-suave);display:inline-flex;align-items:center;justify-content:center;gap:7px;
  white-space:nowrap;text-decoration:none;flex:none;width:auto}
.hef-atualiza .btn:hover{border-color:var(--texto-suave);color:var(--fg)}
.hef-atualiza .btn.principal{background:var(--green);border-color:var(--green);color:var(--app-bg);
  font-weight:600;padding:0 16px}
.hef-atualiza .btn.principal:hover{background:color-mix(in srgb,var(--green) 75%,#fff);
  color:var(--app-bg)}
.hef-atualiza .btn.amarelo-padrao{border-color:var(--yellow);color:var(--yellow)}
.hef-atualiza .btn.amarelo-padrao:hover{background:rgba(241,250,140,.08)}
.hef-atualiza .btn.borda-vermelha{border-color:var(--red);color:var(--red)}
.hef-atualiza .btn.borda-vermelha:hover{background:rgba(255,85,85,.08)}
.hef-atualiza .btn .n{font-family:'JetBrains Mono',monospace;font-size:12px}
.hef-atualiza .tn-cx.mapa{width:min(760px,calc(100vw - 32px));max-height:calc(100vh - 32px)}
.hef-atualiza .tn-cx.larga{width:min(760px,calc(100vw - 32px))}
.hef-atualiza .mapa .tn-topo{padding:10px 18px 9px;gap:16px;
  border-bottom:1px solid var(--border-sutil)}
.hef-atualiza .mapa .tn-tit{font-size:18px;font-weight:700;color:var(--pink)}
.hef-atualiza .mapa .btn.voltar{height:30px}
.hef-atualiza .mapa .tn-corpo,.hef-atualiza .larga .tn-corpo{padding:6px 18px 8px;flex:1}
.hef-atualiza .mapa .tn-rod{padding:9px 18px 11px}
.hef-atualiza .mapa .tn-rod .empurra{flex:1}
.hef-atualiza .btn.apagado{opacity:.45;pointer-events:none}
.hef-atualiza .mp-lista{display:flex;flex-direction:column}
.hef-atualiza .mp-l{display:grid;grid-template-columns:28px minmax(0,1fr) auto 24px 28px;
  align-items:center;gap:12px;height:36px;padding:0 4px;color:var(--fg);
  border-bottom:1px solid var(--border-sutil)}
.hef-atualiza .mp-l:last-child{border-bottom:0}
.hef-atualiza label.mp-l{cursor:pointer}
.hef-atualiza label.mp-l:hover{background:color-mix(in srgb,var(--purple) 6%,transparent)}
.hef-atualiza .mp-i{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;color:var(--texto-suave);background:var(--border-sutil)}
.hef-atualiza .mp-i svg{width:16px;height:16px}
.hef-atualiza .mp-n{font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;min-width:0}
.hef-atualiza .mp-v{font-family:'JetBrains Mono',monospace;font-size:12px;white-space:nowrap;
  color:var(--texto-suave);text-align:right}
.hef-atualiza .mp-v .seta{color:var(--purple);margin:0 5px}
.hef-atualiza .mp-l.nova .mp-v .nv{color:var(--fg);font-weight:500}
.hef-atualiza .mp-s{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font:700 13px/1 'JetBrains Mono',monospace}
.hef-atualiza .mp-s.ok{color:var(--green);box-shadow:inset 0 0 0 1.5px var(--green)}
.hef-atualiza .mp-s.nova{background:var(--purple);color:var(--app-bg)}
.hef-atualiza .mp-s.revisar,.hef-atualiza .mp-s.falhou{background:var(--orange);
  color:var(--app-bg)}
.hef-atualiza .mp-s.esperando{color:var(--yellow);box-shadow:inset 0 0 0 1.5px var(--yellow)}
.hef-atualiza .mp-s.aplicando{color:var(--cyan);box-shadow:inset 0 0 0 1.5px var(--cyan)}
.hef-atualiza .mp-s.fila,.hef-atualiza .mp-s.sem-rede{color:var(--texto-mudo);
  box-shadow:inset 0 0 0 1.5px var(--border-forte)}
.hef-atualiza .mp-l.nova .mp-i{color:var(--purple);
  background:color-mix(in srgb,var(--purple) 18%,transparent)}
.hef-atualiza .mp-l.ok .mp-i{color:var(--green);background:rgba(80,250,123,.10)}
.hef-atualiza .mp-l.sem-rede .mp-n,.hef-atualiza .mp-l.fila .mp-n{color:var(--texto-suave)}
.hef-atualiza .mp-mx{width:28px;height:28px;display:flex;align-items:center;justify-content:center}
.hef-atualiza .mp-m{appearance:none;-webkit-appearance:none;width:18px;height:18px;margin:0;
  cursor:pointer;border-radius:5px;border:1.5px solid var(--linha,#53576f);background:var(--panel);
  display:grid;place-content:center}
.hef-atualiza .mp-m:checked{background:var(--pink);border-color:var(--pink)}
.hef-atualiza .mp-m:checked::after{content:"";width:9px;height:5px;margin-top:-2px;
  border-left:2px solid var(--app-bg);border-bottom:2px solid var(--app-bg);
  transform:rotate(-45deg)}
.hef-atualiza .pendente{display:flex;align-items:center;gap:8px;padding:7px 10px;
  border:1px dashed var(--orange);border-radius:6px;font-size:12px;color:var(--orange);
  background:rgba(255,184,108,.07)}
.hef-atualiza .pendente .jogo{color:var(--fg);font-weight:600}
.hef-atualiza .mp-l .pendente{display:block;padding:3px 9px;line-height:16px;max-width:260px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hef-atualiza .vt-lista{display:flex;flex-direction:column}
.hef-atualiza .vt-l,.hef-atualiza .vt-cab{display:grid;
  grid-template-columns:minmax(0,1fr) 120px 64px 150px;align-items:center;gap:10px}
.hef-atualiza .vt-l{height:40px;border-bottom:1px solid var(--border-sutil);font-size:12.5px;
  color:var(--fg)}
.hef-atualiza .vt-l:last-child{border-bottom:0}
.hef-atualiza .vt-l .v{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--fg)}
.hef-atualiza .vt-l .d{font-family:'JetBrains Mono',monospace;font-size:11.5px;
  color:var(--texto-mudo)}
.hef-atualiza .vt-l .btn{height:30px}
.hef-atualiza .vt-cab{font-size:12px;font-weight:600;color:var(--green);padding-bottom:4px;
  border-bottom:1px solid var(--border-sutil)}
.hef-atualiza .and-total{display:grid;grid-template-columns:minmax(0,1fr) auto;
  align-items:center;gap:12px;height:30px}
.hef-atualiza .and-total .n{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--fg);
  white-space:nowrap}
.hef-atualiza .trilho{height:6px;border-radius:3px;background:var(--border-forte);
  position:relative;flex:1;min-width:0;display:block}
.hef-atualiza .trilho .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;
  background:var(--cyan)}
.hef-atualiza .and-total .trilho .cheio{background:var(--green)}
.hef-atualiza .mp-l .and-barra{width:120px;display:flex;align-items:center}
.hef-atualiza .refaz{color:var(--cyan);margin-right:6px}
.hef-atualiza .and-reinicio{margin-top:10px}
.hef-atualiza .registro{min-height:240px;max-height:360px;overflow:auto;margin:0;padding:8px 10px;
  font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--fg);white-space:pre-wrap;
  border:1px solid var(--border-sutil);border-radius:6px;background:var(--app-bg)}
"""

JS_DA_CAIXA = """(function(css, corpo, id){
  var raiz = document.getElementById(id);
  if(!raiz){
    var folha = document.createElement('style');
    folha.id = id + '-folha';
    folha.textContent = css;
    document.head.appendChild(folha);
    raiz = document.createElement('div');
    raiz.id = id;
    raiz.className = 'hef-atualiza';
    document.body.appendChild(raiz);
  }
  if(raiz.dataset.corpo !== corpo){
    raiz.innerHTML = corpo;
    raiz.dataset.corpo = corpo;
    raiz.querySelectorAll('[data-meio]').forEach(function(c){ c.indeterminate = true; });
    raiz.querySelectorAll('pre.registro').forEach(function(r){ r.scrollTop = r.scrollHeight; });
  }
  raiz.classList.toggle('aberta', corpo !== '');
  return corpo === '' ? 0 : 1;
})(%s, %s, %s)"""


def _e(texto: object) -> str:
    return html.escape(str(texto or ""), quote=True)


def _dica(texto: str) -> str:
    return f' data-dica="{_e(texto)}"' if texto else ""


def _ordenadas(itens: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    por_id = {str(i.get("id")): i for i in itens if isinstance(i, dict)}
    vistas = [por_id[i] for i in ORDEM_NA_TELA if i in por_id]
    vistas += [i for k, i in por_id.items() if k not in ORDEM_NA_TELA]
    return [i for i in vistas if i.get("estado") != "fora"]


def versao_curta(versao: object) -> str:
    """A versão do upstream: sem a época e sem o sufixo da distribuição e da casa."""
    texto = str(versao or "").strip()
    texto = re.sub(r"^\d+:", "", texto)
    return re.split(r"[~+]", texto, maxsplit=1)[0]


def _par_de_versoes(item: dict[str, Any]) -> tuple[str, str]:
    de, para = str(item.get("de") or ""), str(item.get("para") or "")
    if item.get("estado") in ("nova", "revisar") and de and para and de != para:
        return de, para
    return "", de or para


def _versao_a_vista(item: dict[str, Any]) -> str:
    if item.get("rotulo"):
        return f'<span class="nv">{_e(item["rotulo"])}</span>'
    de, agora = _par_de_versoes(item)
    if de:
        return (f'{_e(versao_curta(de))}<span class="seta">→</span>'
                f'<span class="nv">{_e(versao_curta(agora))}</span>')
    return f'<span class="nv">{_e(versao_curta(agora))}</span>' if agora else ""


def _versao_inteira(item: dict[str, Any]) -> str:
    if item.get("completa"):
        return str(item["completa"])
    de, agora = _par_de_versoes(item)
    if de:
        return f"{de} → {agora}"
    return agora if versao_curta(agora) != agora else ""


def _icone(ident: str) -> str:
    desenho = ICONES.get(ident, ICONES[""])
    return (f'<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
            f'{desenho}</svg>')


def _grupo_do_cartao(item: dict[str, Any]) -> str:
    estado = str(item.get("estado") or "")
    estado = GRUPO_DO_ESTADO.get(estado, estado)
    return estado if estado in ESTADOS_DO_MAPA else "sem_rede"


def marcavel(item: dict[str, Any]) -> bool:
    """A peça com versão nova se atualiza; a em dia e a de revisar se reinstalam, se o motor
    deixa."""
    if item.get("volta", 1) != 1:
        return False
    grupo = _grupo_do_cartao(item)
    return grupo == "nova" or (grupo in REINSTALAVEIS and item.get("reinstala", True) is not False)


def e_reinstalacao(item: dict[str, Any]) -> bool:
    return marcavel(item) and _grupo_do_cartao(item) != "nova"


def marcada(item: dict[str, Any]) -> bool:
    if not marcavel(item):
        return False
    return bool(item.get("reinstalar" if e_reinstalacao(item) else "marcada"))


def _por_que_sem_marca(item: dict[str, Any]) -> str:
    if _grupo_do_cartao(item) == "sem_rede":
        return DICA_SEM_REDE
    return str(item.get("motivo") or DICA_SEM_REINSTALAR)


def _junto(*partes: str) -> str:
    return " · ".join(x for x in partes if x)


def _selo(classe: str, dica: str) -> str:
    return f'<span class="mp-s {classe}"{_dica(dica)}>{GLIFO[classe]}</span>'


def _linha(item: dict[str, Any], classe: str, dica_do_selo: str, meio: str, fim: str,
           dica: str, *, marca: bool = False) -> str:
    """Uma linha: o ícone, o nome e a versão (a explicação na dica), o meio, o selo e a marca."""
    tag = "label" if marca else "div"
    return (f'<{tag} class="mp-l {classe}"><span class="mp-i">'
            f'{_icone(str(item.get("id") or ""))}</span>'
            f'<span class="mp-n"{_dica(dica)}>{_e(item.get("nome"))}</span>'
            f'{meio}{_selo(classe, dica_do_selo)}<span class="mp-mx">{fim}</span></{tag}>')


def _linha_do_mapa(item: dict[str, Any]) -> str:
    classe, estado = ESTADO_DO_MAPA[_grupo_do_cartao(item)]
    versao = f'<span class="mp-v">{_versao_a_vista(item)}</span>'
    if not marcavel(item):
        dica = _junto(str(item.get("dica") or ""), _versao_inteira(item), _por_que_sem_marca(item))
        return _linha(item, classe, estado, versao, "", dica)
    reinstala = DICA_DA_REINSTALACAO if e_reinstalacao(item) else ""
    caixa = (f'<input type="checkbox" class="mp-m"{" checked" if marcada(item) else ""}'
             f' data-gesto="peca-da-atualizacao" data-v="{_e(item["id"])}">')
    dica = _junto(str(item.get("dica") or ""), _versao_inteira(item), reinstala)
    return _linha(item, classe, estado, versao, caixa, dica, marca=True)


def html_do_mapa(conferencia: dict[str, Any]) -> str:
    """Uma linha por peça: o nome, a versão de agora → a nova, o estado e a marca."""
    itens = _ordenadas(conferencia.get("pecas") or [])
    return f'<div class="mp-lista">{"".join(_linha_do_mapa(i) for i in itens)}</div>'


def ids_para_atualizar(conferencia: dict[str, Any]) -> list[str]:
    return [str(i["id"]) for i in _ordenadas(conferencia.get("pecas") or []) if marcada(i)]


def html_da_pergunta(conferencia: dict[str, Any], escolha: dict[str, Any], *,
                     jogo_aberto: bool, nome_do_jogo: str = "", fila_espera: bool = False) -> str:
    """O mapa das atualizações: o topo, as linhas e o rodapé com o «Atualizar tudo»."""
    n = len(ids_para_atualizar(conferencia))
    jogo = (f'<span>Jogo aberto:</span><span class="jogo">{_e(nome_do_jogo)}</span>'
            if nome_do_jogo else '<span>Jogo aberto</span>')
    pendente = (f'<div class="pendente">{jogo}<span>· espera</span></div>'
                if jogo_aberto else "")
    apagado = "" if n and not fila_espera else " apagado"
    dica = DICA_DA_FILA if fila_espera else DICA_DO_JOGO if jogo_aberto else ""
    principal = (f'<button class="btn principal{apagado}" data-gesto="atualizacoes-atualizar"'
                 f'{_dica(dica)}>'
                 f'{ROTULO_DO_ATUALIZAR} <span class="n">{n}</span></button>')
    auto = " auto" if escolha.get("sozinho") else ""
    return (f'<div class="tn-cx mapa{auto}" role="dialog" aria-modal="true" '
            f'aria-label="Atualizações">'
            f'<div class="tn-topo"><button class="btn voltar" data-gesto="atualizacoes-fechar">'
            f'← Voltar</button><span class="tn-tit">Atualizações</span>'
            f'</div><div class="tn-corpo">{html_do_mapa(conferencia)}</div>'
            f'<div class="tn-rod">'
            f'<button class="btn" data-gesto="atualizacoes-anteriores">Versões anteriores</button>'
            f'<span class="empurra"></span>{pendente}'
            f'<button class="btn" data-gesto="atualizacoes-agora-nao">Agora não</button>'
            f'{principal}</div></div>')


def _data(segundos: object) -> str:
    try:
        return time.strftime("%d/%m", time.localtime(float(str(segundos))))
    except (TypeError, ValueError, OverflowError):
        return ""


def html_das_anteriores(anteriores: dict[str, Any], pode_voltar: Sequence[str]) -> str:
    """As versões anteriores: peça, a de agora, desde quando, e o botão que volta."""
    linhas = []
    for ident in ORDEM_NA_TELA:
        dado = anteriores.get(ident)
        if ident not in pode_voltar or not isinstance(dado, dict) \
                or not (dado.get("anterior") or dado.get("rotulo")):
            continue
        dica = _dica("No próximo início") if ident == "kernel" else ""
        anterior = versao_curta(dado.get("anterior"))
        agora = str(dado.get("rotulo") or "") if not anterior else versao_curta(dado.get("agora"))
        linhas.append(
            f'<div class="vt-l"><span>{_e(dado.get("nome") or ident)}</span>'
            f'<span class="v"{_dica(str(dado.get("agora") or ""))}>'
            f'{_e(agora)}</span>'
            f'<span class="d">{_data(dado.get("desde"))}'
            f'</span><button class="btn amarelo-padrao" data-gesto="voltar-a-anterior" '
            f'data-v="{_e(ident)}"{dica}>{f"Voltar a {_e(anterior)}" if anterior else "Voltar"}'
            f'</button></div>')
    return (f'<div class="tn-cx" role="dialog" aria-modal="true" aria-label="Atualizações">'
            f'<div class="tn-topo"><span class="tn-tit">Atualizações</span>'
            f'<span class="tn-tit">· Versões anteriores</span>'
            f'<button class="tn-x" data-gesto="atualizacoes-fechar"{_dica("Fechar")}>&times;'
            f'</button></div>'
            f'<div class="tn-corpo"><div class="vt-lista"><div class="vt-cab"><span>Peça</span>'
            f'<span>Agora</span><span>Desde</span><span></span></div>{"".join(linhas)}</div></div>'
            f'<div class="tn-rod"><button class="btn" data-gesto="atualizacoes-lista">'
            f'← Atualizações</button></div></div>')


def _barra(pct: object, dica: str = "") -> str:
    try:
        valor = max(0, min(100, round(float(str(pct)))))
    except (TypeError, ValueError):
        valor = 0
    return (f'<span class="and-barra"{_dica(dica)}><span class="trilho">'
            f'<span class="cheio" style="width:{valor}%"></span></span></span>')


def _etapa_agora(etapas: object) -> str:
    if not isinstance(etapas, dict):
        return ""
    return next((ETAPA_NA_DICA.get(str(k), str(k)) for k, v in etapas.items() if v == "agora"), "")


def _linha_do_andamento(peca: dict[str, Any], *, parada: bool = False) -> str:
    """A linha do mapa, com o estado da fila: a barra só na peça em curso, o porquê na dica."""
    selo = str(peca.get("selo") or "fila")
    classe, estado = ESTADO_DO_ANDAMENTO.get(selo, ("fila", NA_FILA))
    if parada and classe in ("fila", "aplicando"):
        classe, estado = "fila", PARADA
    motivo = str(peca.get("motivo") or "")
    if classe == "aplicando":
        estado = _junto(estado, _etapa_agora(peca.get("etapas")))
    elif classe in ("esperando", "falhou", "ok", "fila") and motivo:
        estado = f"{estado}: {motivo}"
    de, para = str(peca.get("de") or ""), str(peca.get("para") or "")
    if peca.get("fazer") == "reinstalar":
        ver = (f'<span class="refaz"{_dica("Reinstala")}>{GLIFO_DA_REINSTALACAO}</span>'
               f'<span class="nv">{_e(peca.get("rotulo") or versao_curta(de or para))}</span>')
    elif peca.get("rotulo"):
        ver = f'<span class="nv">{_e(peca["rotulo"])}</span>'
    elif de and para and de != para:
        ver = (f'{_e(versao_curta(de))}<span class="seta">→</span>'
               f'<span class="nv">{_e(versao_curta(para))}</span>')
    else:
        ver = f'<span class="nv">{_e(versao_curta(para or de))}</span>'
    contagens = _junto(*(f'{c.get("qual")} {c.get("feitos", 0)}/{c.get("de", 0)}'
                         for c in peca.get("contagens") or [] if isinstance(c, dict)))
    barra = _barra(peca.get("pct", 0), contagens) if classe == "aplicando" else ""
    meio = f'<span class="mp-v">{barra or ver}</span>'
    if classe == "esperando" and motivo:
        meio = f'<span class="pendente">{_e(motivo[:1].upper() + motivo[1:])}</span>'
    dica = _junto(_versao_inteira({"de": de, "para": para, "estado": "nova"}),
                  str(peca.get("dica_do_aplicar") or ""))
    return _linha(peca, classe, estado, meio, "", dica)


def html_do_andamento(andamento: dict[str, Any], *, rodando: bool, parando: bool = False,
                      pede_reinicio: str = "", fecha_a_steam: bool = False) -> str:
    """O total, uma linha por peça e o reinício do serviço; o rodapé muda com a fila."""
    parada = not rodando and andamento.get("fase") == "parado"
    pecas = _ordenadas([p for p in andamento.get("pecas") or [] if isinstance(p, dict)])
    total = andamento.get("total") or {}
    feitas, de, pct = int(total.get("feitas", 0)), int(total.get("de", len(pecas))), \
        int(total.get("pct", 0))
    falhas = int(total.get("falhas", 0))
    reinicio = andamento.get("reinicio") or {}
    servico = {"id": "hefesto", "nome": "Serviço", "selo": reinicio.get("selo") or "fila",
               "etapas": reinicio.get("etapas") or {}, "pct": reinicio.get("pct", 0)}
    botoes = [f'<button class="btn" data-gesto="atualizacoes-registro"{_dica(DICA_DO_REGISTRO)}>'
              'Registro</button>']
    empurra = " empurra"
    if rodando and fecha_a_steam and andamento.get("fase") in ("espera", "espera_o_jogo"):
        botoes.append('<button class="btn empurra" data-gesto="atualizacoes-fechar-a-steam">'
                      'Fechar e continuar</button>')
        empurra = ""
    if falhas:
        botoes.append(f'<button class="btn{empurra}" data-gesto="atualizacoes-tentar">'
                      'Tentar de novo</button>')
        empurra = ""
    if parada:
        botoes.append(f'<button class="btn{empurra}" data-gesto="atualizacoes-continuar">'
                      'Continuar</button>')
    elif pede_reinicio and not rodando:
        botoes.append(f'<button class="btn borda-vermelha{empurra}" '
                      f'data-gesto="atualizacoes-reiniciar-o-computador"{_dica(pede_reinicio)}>'
                      'Reiniciar agora</button>')
    if rodando:
        botoes.append(f'<button class="btn borda-vermelha{empurra}" '
                      f'data-gesto="atualizacoes-parar"{" disabled" if parando else ""}>'
                      f'{PARANDO if parando else "Parar"}</button>')
    titulo = f"Atualizações · {PARADA}" if parada else "Atualizações"
    aviso = (f'<div class="pendente and-reinicio"{_dica(pede_reinicio)}>{REINICIE}</div>'
             if pede_reinicio and not rodando else "")
    return (f'<div class="tn-cx larga" role="dialog" aria-modal="true" aria-label="Atualizações">'
            f'<div class="tn-topo"><span class="tn-tit">{titulo}</span>'
            f'<button class="tn-x" data-gesto="atualizacoes-fechar"'
            f'{_dica("Esconder" if rodando else "Fechar")}>&times;</button>'
            f'</div><div class="tn-corpo"><div class="and-total">'
            f'<span class="trilho"><span class="cheio" style="width:{pct}%"></span></span>'
            f'<span class="n">{feitas} de {de}</span></div>'
            f'<div class="mp-lista">'
            f'{"".join(_linha_do_andamento(p, parada=parada) for p in pecas)}'
            f'{_linha_do_andamento(servico, parada=parada)}</div>{aviso}</div>'
            f'<div class="tn-rod">{"".join(botoes)}</div></div>')


def html_do_registro(texto: str) -> str:
    """O registro da atualização dentro da caixa, com Copiar e Salvar."""
    return (f'<div class="tn-cx larga" role="dialog" aria-modal="true" aria-label="Registro">'
            f'<div class="tn-topo"><span class="tn-tit">Registro</span>'
            f'<button class="tn-x" data-gesto="atualizacoes-fechar"{_dica("Fechar")}>'
            f'&times;</button></div><div class="tn-corpo">'
            f'<pre class="registro">{_e(texto) or "Nada registrado ainda."}</pre></div>'
            f'<div class="tn-rod"><button class="btn" data-gesto="atualizacoes-registro-voltar">'
            f'← Atualizações</button>'
            f'<button class="btn empurra" data-gesto="atualizacoes-registro-copiar">Copiar</button>'
            f'<button class="btn" data-gesto="atualizacoes-registro-salvar">Salvar</button>'
            f'</div></div>')


def quantas_novas(conferencia: dict[str, Any]) -> int:
    return sum(1 for i in _ordenadas(conferencia.get("pecas") or []) if i.get("estado") == "nova")


def js_da_caixa(corpo: str) -> str:
    return JS_DA_CAIXA % (json.dumps(CSS), json.dumps(corpo), json.dumps(ID_DA_CAIXA))
