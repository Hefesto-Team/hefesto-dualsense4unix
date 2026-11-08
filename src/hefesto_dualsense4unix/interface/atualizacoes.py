"""A pergunta da atualização e o andamento, como o arranjo A do desenho.

O desenho é ``mockup/escolha/a-pergunta-da-atualizacao.html``. O arranjo A: a lista única com o
Hefesto em cima e as peças de fora num grupo marcável, o «Atualizar sozinho» e o prazo embaixo;
as versões anteriores; e o andamento com o total, uma barra por peça e o
reinício do serviço no fim. A caixa nasce por cima de qualquer aba (``JS_DA_CAIXA``) e se repinta
inteira a cada mudança; a grade da aba Sistema (``grade_da_aba``) é a mesma conferência em três
colunas. Puro: recebe os dicionários do motor e devolve HTML.
"""
from __future__ import annotations

import html
import json
import time
from collections.abc import Sequence
from typing import Any

ID_DA_CAIXA = "hef-atualizacoes"
ORDEM_NA_TELA = ("hefesto", "proton", "bluetooth", "som", "portal", "gdk", "python", "nvidia",
                 "kernel", "dkms", "sistema", "mangohud", "umu")
COLUNAS_DA_GRADE = (4, 3, 3, 3)
ROTULO_DO_GRUPO = "Bibliotecas, drivers e plugins"
DICA_DO_SOZINHO = "Sem pergunta, só com o jogo fechado"
DICA_DO_PRAZO = "Prazo da conferência"
DICA_DO_REGISTRO = "O registro desta atualização"
DICA_DA_FIXA = "Sobe junto com o Hefesto"
ETAPAS_NA_TELA = (("baixar", "Baixar"), ("instalar", "Instalar"), ("aplicar", "Aplicar em todos"))
ETAPAS_DO_REINICIO = (("reiniciar", "Reiniciar o serviço"), ("reabrir", "Reabrir o Hefesto"))
SELO_DO_ANDAMENTO = {"fila": ("fila", "NA FILA"), "baixando": ("baixando", "BAIXANDO"),
                     "instalando": ("instalando", "INSTALANDO"),
                     "aplicando": ("aplicando", "APLICANDO"), "pronta": ("ok", "PRONTA"),
                     "falhou": ("falhou", "FALHOU"), "reiniciando": ("aplicando", "REINICIANDO")}

CSS = """
.hef-atualiza{display:none;position:fixed;inset:0;z-index:70;background:rgba(9,10,15,.72);
  align-items:center;justify-content:center;font-family:'Space Grotesk',system-ui,sans-serif}
.hef-atualiza.aberta{display:flex}
.hef-atualiza .tn-cx{width:660px;max-width:94vw;background:var(--panel);border-radius:11px;
  border:1px solid var(--border-forte);box-shadow:0 26px 70px rgba(0,0,0,.62);display:flex;
  flex-direction:column;max-height:min(717px,calc(100vh - 40px))}
.hef-atualiza .tn-cx.larga{width:900px}
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
.hef-atualiza .btn .n{font-family:'JetBrains Mono',monospace;font-size:11.5px}
.hef-atualiza .cadeado{display:inline-flex;align-items:center;justify-content:center;gap:9px;
  height:var(--h-acao,34px);white-space:nowrap;border-radius:999px;padding:0 16px 0 12px;width:auto;
  font:600 12.5px/1 'Space Grotesk',system-ui,sans-serif;cursor:pointer;
  border:1px solid var(--border-forte);background:var(--app-bg);color:var(--fg)}
.hef-atualiza .cadeado .p{width:10px;height:10px;border-radius:50%;flex:0 0 auto;
  background:var(--border-forte)}
.hef-atualiza .cadeado.ligada{border-color:var(--green);background:rgba(80,250,123,.09);
  color:var(--green)}
.hef-atualiza .cadeado.ligada .p{background:var(--green);box-shadow:0 0 6px var(--green)}
.hef-atualiza .prazo{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;
  color:var(--fg);white-space:nowrap}
.hef-atualiza .prazo .pm{width:28px;height:28px;border-radius:6px;
  border:1px solid var(--linha,#53576f);background:var(--app-bg);color:var(--fg);
  font:600 14px/1 'JetBrains Mono',monospace;cursor:pointer}
.hef-atualiza .prazo .pm:hover{border-color:var(--comment)}
.hef-atualiza .prazo .dias{min-width:26px;text-align:center;font-family:'JetBrains Mono',monospace;
  font-weight:500;color:var(--cyan)}
.hef-atualiza .selo{font-size:11px;padding:2px 7px;border-radius:4px;font-weight:600;
  font-family:'JetBrains Mono',monospace;white-space:nowrap;text-align:center;flex:none}
.hef-atualiza .selo.nova{background:var(--purple);color:var(--app-bg)}
.hef-atualiza .selo.ok{background:transparent;color:var(--green);
  box-shadow:inset 0 0 0 1px var(--green)}
.hef-atualiza .selo.fila{background:transparent;color:var(--texto-mudo);
  box-shadow:inset 0 0 0 1px var(--border-forte)}
.hef-atualiza .selo.baixando{background:var(--cyan);color:var(--app-bg)}
.hef-atualiza .selo.instalando{background:var(--purple);color:var(--app-bg)}
.hef-atualiza .selo.aplicando{background:var(--pink);color:var(--app-bg)}
.hef-atualiza .selo.falhou{background:var(--red);color:var(--app-bg)}
.hef-atualiza .at-lista{display:flex;flex-direction:column}
.hef-atualiza .at-l{display:grid;grid-template-columns:22px minmax(0,1fr) auto 84px;
  align-items:center;gap:10px;height:34px;border-bottom:1px solid var(--border-sutil);
  font-size:12.5px;cursor:pointer;color:var(--fg)}
.hef-atualiza .at-l:last-child{border-bottom:0}
.hef-atualiza .tn-cx:has(.pendente) .at-l{height:32px}
.hef-atualiza .at-l input{width:16px;height:16px;accent-color:var(--pink);margin:0;cursor:pointer}
.hef-atualiza .at-l .at-ok{color:var(--green);font-size:13px;text-align:center;width:16px}
.hef-atualiza .at-l.filho{padding-left:26px}
.hef-atualiza .at-l.grupo .at-n{font-weight:600}
.hef-atualiza .at-l .at-n{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hef-atualiza .at-l .at-n .q{color:var(--texto-mudo);font-weight:400;margin-left:6px}
.hef-atualiza .at-l .at-v{font-family:'JetBrains Mono',monospace;font-size:12px;
  color:var(--texto-suave);text-align:right;white-space:nowrap}
.hef-atualiza .at-v .seta{color:var(--purple);margin:0 4px}
.hef-atualiza .and-l .ver .seta{color:var(--purple);margin:0 3px}
.hef-atualiza .at-v .nv{color:var(--fg);font-weight:500}
.hef-atualiza .at-l.de-fora .at-n,.hef-atualiza .at-l.de-fora .at-v,
.hef-atualiza .at-l.de-fora .at-v .nv{color:var(--texto-mudo)}
.hef-atualiza .sep-lista{height:8px}
.hef-atualiza .at-ajuste{display:flex;align-items:center;gap:14px;padding-top:10px;
  border-top:1px solid var(--border-sutil)}
.hef-atualiza .pendente{display:flex;align-items:center;gap:8px;padding:7px 10px;
  border:1px dashed var(--orange);border-radius:6px;font-size:12px;color:var(--orange);
  background:rgba(255,184,108,.07)}
.hef-atualiza .pendente .jogo{color:var(--fg);font-weight:600}
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
.hef-atualiza .and-total{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;
  align-items:center;gap:12px;height:34px}
.hef-atualiza .and-total .rot{font-size:12px;font-weight:600;color:var(--green)}
.hef-atualiza .and-total .n{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--fg);
  white-space:nowrap}
.hef-atualiza .and-total .n.erro{color:var(--red)}
.hef-atualiza .trilho{height:6px;border-radius:3px;background:var(--border-forte);
  position:relative;flex:1;min-width:0;display:block}
.hef-atualiza .trilho .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;
  background:var(--purple)}
.hef-atualiza .and-total .trilho{height:8px;border-radius:4px}
.hef-atualiza .and-total .trilho .cheio{border-radius:4px;background:var(--green)}
.hef-atualiza .and-lista{display:flex;flex-direction:column;
  border-top:1px solid var(--border-sutil)}
.hef-atualiza .and-l{display:grid;grid-template-columns:104px 112px 300px minmax(0,1fr) 96px;
  align-items:center;gap:10px;height:40px;border-bottom:1px solid var(--border-sutil);
  font-size:12.5px;color:var(--fg)}
.hef-atualiza .and-l:last-child{border-bottom:0}
.hef-atualiza .and-l .nome{font-weight:600;white-space:nowrap}
.hef-atualiza .and-l .ver{font-family:'JetBrains Mono',monospace;font-size:11.5px;
  color:var(--texto-suave);white-space:nowrap}
.hef-atualiza .and-l .ver .nv{color:var(--fg)}
.hef-atualiza .etapas{display:flex;gap:14px}
.hef-atualiza .etp{height:24px;font-size:12px;display:inline-flex;align-items:center;gap:5px;
  color:var(--texto-mudo);white-space:nowrap}
.hef-atualiza .etp::before{content:"○";font-size:10px}
.hef-atualiza .etp.feito{color:var(--green)}
.hef-atualiza .etp.feito::before{content:"✓";font-size:11px}
.hef-atualiza .etp.agora{color:var(--cyan);font-weight:600}
.hef-atualiza .etp.agora::before{content:"●";font-size:9px}
.hef-atualiza .etp.erro{color:var(--red);font-weight:600}
.hef-atualiza .etp.erro::before{content:"✕";font-size:10px}
.hef-atualiza .and-barra{display:flex;align-items:center;gap:8px;min-width:0}
.hef-atualiza .and-barra .n{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--fg);
  flex:0 0 46px;text-align:right;white-space:nowrap}
.hef-atualiza .and-barra.pronta .cheio{background:var(--green)}
.hef-atualiza .and-barra.falhou .cheio{background:var(--red)}
.hef-atualiza .and-barra.falhou .n{color:var(--red)}
.hef-atualiza .and-multi{display:flex;flex-direction:column;gap:3px;min-width:0}
.hef-atualiza .and-multi .and-barra{gap:6px}
.hef-atualiza .and-multi .qual{flex:0 0 44px;font-size:11px;color:var(--texto-suave)}
.hef-atualiza .and-multi .n{flex:0 0 40px;font-size:11px}
.hef-atualiza .and-multi .trilho{height:4px}
.hef-atualiza .and-l.na-fila .nome,.hef-atualiza .and-l.na-fila .ver,
.hef-atualiza .and-l.na-fila .ver .nv{color:var(--texto-mudo)}
.hef-atualiza .and-l.reinicio{border-top:1px solid var(--linha,#53576f)}
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


def _ver(item: dict[str, Any]) -> str:
    de, para = str(item.get("de") or ""), str(item.get("para") or "")
    if item.get("rotulo"):
        return f'<span class="rot">{_e(item["rotulo"])}</span>'
    if item.get("estado") == "nova" and de and para:
        return (f'<span class="de">{_e(de)}</span><span class="seta">→</span>'
                f'<span class="nv">{_e(para)}</span>')
    atual = de or para
    return f'<span class="nv">{_e(atual)}</span>' if atual else ""


def _ver_inteira(item: dict[str, Any]) -> str:
    de, para = str(item.get("de") or ""), str(item.get("para") or "")
    if item.get("rotulo"):
        return str(item["rotulo"])
    if item.get("estado") == "nova" and de and para:
        return f"{de} → {para}"
    return ""


def _selo_da_pergunta(item: dict[str, Any]) -> str:
    estado = item.get("estado")
    if estado == "nova":
        return '<span class="selo nova">NOVA</span>'
    if estado == "em_dia":
        return '<span class="selo ok">EM DIA</span>'
    if estado == "fixa":
        return f'<span class="selo fila"{_dica(DICA_DA_FIXA)}>FIXA</span>'
    return f'<span class="selo fila"{_dica(item.get("dica", ""))}>SEM REDE</span>'


def _linha_da_pergunta(item: dict[str, Any], classe: str) -> str:
    nova = item.get("estado") == "nova"
    marcada = bool(item.get("marcada"))
    if nova:
        caixa = (f'<input type="checkbox"{" checked" if marcada else ""} '
                 f'data-gesto="peca-da-atualizacao" data-v="{_e(item["id"])}">')
        extra = "" if marcada else " de-fora"
    else:
        em_dia = item.get("estado") == "em_dia"
        caixa = '<span class="at-ok">✓</span>' if em_dia else "<span></span>"
        extra = ""
    return (f'<label class="at-l {classe}{extra}">{caixa}'
            f'<span class="at-n"{_dica(item.get("dica", ""))}>{_e(item.get("nome"))}</span>'
            f'<span class="at-v">{_ver(item)}</span>{_selo_da_pergunta(item)}</label>')


def ids_para_atualizar(conferencia: dict[str, Any]) -> list[str]:
    return [str(i["id"]) for i in _ordenadas(conferencia.get("pecas") or [])
            if i.get("estado") == "nova" and i.get("marcada")]


def html_da_pergunta(conferencia: dict[str, Any], escolha: dict[str, Any], *,
                     jogo_aberto: bool, nome_do_jogo: str = "") -> str:
    """O arranjo A: Hefesto, o grupo das peças de fora, o ajuste e o rodapé."""
    itens = _ordenadas(conferencia.get("pecas") or [])
    do_hefesto = [i for i in itens if i.get("grupo") == "hefesto"]
    de_fora = [i for i in itens if i.get("grupo") != "hefesto"]
    novas_de_fora = [i for i in de_fora if i.get("estado") == "nova"]
    marcadas_de_fora = [i for i in novas_de_fora if i.get("marcada")]
    linhas = [_linha_da_pergunta(i, "grupo") for i in do_hefesto]
    if de_fora:
        linhas.append('<div class="sep-lista"></div>')
        todas = bool(novas_de_fora) and len(marcadas_de_fora) == len(novas_de_fora)
        meio = " data-meio" if marcadas_de_fora and not todas else ""
        mae = (f'<input type="checkbox" data-gesto="pecas-do-grupo" '
               f'data-v="{0 if todas else 1}"{" checked" if todas else ""}{meio}>'
               if novas_de_fora else "<span></span>")
        conta = (f'<span class="q">{len(marcadas_de_fora)} de {len(novas_de_fora)}</span>'
                 if novas_de_fora else "")
        linhas.append(f'<label class="at-l grupo">{mae}<span class="at-n">{ROTULO_DO_GRUPO}'
                      f'{conta}</span><span class="at-v"></span><span></span></label>')
        linhas.extend(_linha_da_pergunta(i, "filho") for i in de_fora)
    n = len(ids_para_atualizar(conferencia))
    sozinho = " ligada" if escolha.get("sozinho") else ""
    ajuste = (f'<div class="at-ajuste"><button class="cadeado{sozinho}" '
              f'data-gesto="atualizar-sozinho"'
              f'{_dica(DICA_DO_SOZINHO)}><span class="p"></span>Atualizar sozinho</button>'
              f'<span class="prazo"{_dica(DICA_DO_PRAZO)}><span>A cada</span>'
              f'<button class="pm" data-gesto="prazo-da-atualizacao" data-v="-1" '
              f'aria-label="Menos um dia">&minus;</button>'
              f'<span class="dias">{_e(escolha.get("dias", 7))}'
              f'</span><button class="pm" data-gesto="prazo-da-atualizacao" data-v="1" '
              f'aria-label="Mais um dia">+</button><span>dias</span></span></div>')
    jogo = (f'<span>Jogo aberto:</span><span class="jogo">{_e(nome_do_jogo)}</span>'
            if nome_do_jogo else '<span>Jogo aberto</span>')
    pendente = (f'<div class="pendente">{jogo}<span>· espera</span></div>'
                if jogo_aberto else "")
    principal = ('<button class="btn principal" data-gesto="atualizacoes-atualizar">'
                 'Atualizar ao fechar o jogo</button>' if jogo_aberto else
                 f'<button class="btn principal" data-gesto="atualizacoes-atualizar">'
                 f'Atualizar <span class="n">{n}</span></button>')
    return (f'<div class="tn-cx" role="dialog" aria-modal="true" aria-label="Atualizações">'
            f'<div class="tn-topo"><span class="tn-tit">Atualizações</span>'
            f'<button class="tn-x" data-gesto="atualizacoes-fechar"{_dica("Fechar")}>&times;'
            f'</button></div>'
            f'<div class="tn-corpo"><div class="at-lista">{"".join(linhas)}</div>{ajuste}{pendente}'
            f'</div><div class="tn-rod">'
            f'<button class="btn" data-gesto="atualizacoes-anteriores">Versões anteriores</button>'
            f'<button class="btn empurra" data-gesto="atualizacoes-agora-nao">Agora não</button>'
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
        if ident not in pode_voltar or not isinstance(dado, dict) or not dado.get("anterior"):
            continue
        dica = _dica("No próximo início") if ident == "kernel" else ""
        linhas.append(
            f'<div class="vt-l"><span>{_e(dado.get("nome") or ident)}</span>'
            f'<span class="v">{_e(dado.get("agora"))}</span>'
            f'<span class="d">{_data(dado.get("desde"))}'
            f'</span><button class="btn amarelo-padrao" data-gesto="voltar-a-anterior" '
            f'data-v="{_e(ident)}"{dica}>Voltar a {_e(dado.get("anterior"))}</button></div>')
    return (f'<div class="tn-cx" role="dialog" aria-modal="true" aria-label="Atualizações">'
            f'<div class="tn-topo"><span class="tn-tit">Atualizações</span>'
            f'<span class="tn-tit">· Versões anteriores</span>'
            f'<button class="tn-x" data-gesto="atualizacoes-fechar"{_dica("Fechar")}>&times;'
            f'</button></div>'
            f'<div class="tn-corpo"><div class="vt-lista"><div class="vt-cab"><span>Peça</span>'
            f'<span>Agora</span><span>Desde</span><span></span></div>{"".join(linhas)}</div></div>'
            f'<div class="tn-rod"><button class="btn" data-gesto="atualizacoes-lista">'
            f'← Atualizações</button></div></div>')


def _etapas(estados: dict[str, Any], nomes: Sequence[tuple[str, str]], dica_do_aplicar: str) -> str:
    saida = []
    for chave, rotulo in nomes:
        classe = {"feito": " feito", "agora": " agora", "erro": " erro"}.get(
            str(estados.get(chave, "")), "")
        dica = _dica(dica_do_aplicar) if chave == "aplicar" else ""
        saida.append(f'<span class="etp{classe}"{dica}>{rotulo}</span>')
    return f'<span class="etapas">{"".join(saida)}</span>'


def _barra(pct: object, classe: str, dica: str = "", *, mostra: bool = True) -> str:
    try:
        valor = max(0, min(100, round(float(str(pct)))))
    except (TypeError, ValueError):
        valor = 0
    cheio = f'<span class="cheio" style="width:{valor}%"></span>' if mostra else ""
    numero = f"{valor}%" if mostra else ""
    return (f'<span class="and-barra{classe}"{_dica(dica)}><span class="trilho">{cheio}</span>'
            f'<span class="n">{numero}</span></span>')


def _linha_do_andamento(peca: dict[str, Any]) -> str:
    selo = str(peca.get("selo") or "fila")
    classe_do_selo, texto = SELO_DO_ANDAMENTO.get(selo, ("fila", selo.upper()))
    motivo = str(peca.get("motivo") or "") if selo == "falhou" else ""
    na_fila = selo == "fila"
    de, para = str(peca.get("de") or ""), str(peca.get("para") or "")
    if peca.get("rotulo"):
        ver = _e(peca["rotulo"])
    elif de and para and de != para:
        ver = f'{_e(de)}<span class="seta">→</span><span class="nv">{_e(para)}</span>'
    else:
        ver = f'<span class="nv">{_e(para or de)}</span>'
    dica_do_aplicar = str(peca.get("dica_do_aplicar", ""))
    contagens = [c for c in peca.get("contagens") or [] if isinstance(c, dict)]
    if contagens and not na_fila:
        barras = []
        for c in contagens:
            de_n, feitos = int(c.get("de") or 0), int(c.get("feitos") or 0)
            pct = 100 if de_n == 0 else round(100 * feitos / de_n)
            pronta = " pronta" if de_n and feitos >= de_n else ""
            barras.append(f'<span class="and-barra{pronta}"><span class="qual">{_e(c.get("qual"))}'
                          f'</span><span class="trilho"><span class="cheio" style="width:{pct}%">'
                          f'</span></span><span class="n">{feitos}/{de_n}</span></span>')
        barra = f'<span class="and-multi">{"".join(barras)}</span>'
    else:
        classe = {"pronta": " pronta", "falhou": " falhou"}.get(selo, "")
        barra = _barra(peca.get("pct", 0), classe, motivo, mostra=not na_fila)
    return (f'<div class="and-l{" na-fila" if na_fila else ""}">'
            f'<span class="nome"{_dica(motivo)}>{_e(peca.get("nome"))}</span>'
            f'<span class="ver">{ver}</span>'
            f'{_etapas(peca.get("etapas") or {}, ETAPAS_NA_TELA, dica_do_aplicar)}'
            f'{barra}<span class="selo {classe_do_selo}"{_dica(motivo)}>{texto}</span></div>')


def html_do_andamento(andamento: dict[str, Any], *, rodando: bool) -> str:
    """O total, uma linha por peça e o reinício do serviço; o rodapé muda com a fila."""
    pecas = [p for p in andamento.get("pecas") or [] if isinstance(p, dict)]
    total = andamento.get("total") or {}
    feitas, de, pct = int(total.get("feitas", 0)), int(total.get("de", len(pecas))), \
        int(total.get("pct", 0))
    falhas = int(total.get("falhas", 0))
    erro = f'<span class="n erro">{falhas} falhou</span>' if falhas else "<span></span>"
    reinicio = andamento.get("reinicio") or {}
    selo_r = str(reinicio.get("selo") or "fila")
    classe_r, texto_r = SELO_DO_ANDAMENTO.get(selo_r, ("fila", selo_r.upper()))
    fila_r = selo_r == "fila"
    classe_da_barra = " pronta" if selo_r == "pronta" else ""
    linha_r = (f'<div class="and-l reinicio{" na-fila" if fila_r else ""}">'
               f'<span class="nome">Serviço</span><span class="ver"></span>'
               f'{_etapas(reinicio.get("etapas") or {}, ETAPAS_DO_REINICIO, "")}'
               f'{_barra(reinicio.get("pct", 0), classe_da_barra, mostra=not fila_r)}'
               f'<span class="selo {classe_r}">{texto_r}</span></div>')
    botoes = [f'<button class="btn" data-gesto="atualizacoes-registro"{_dica(DICA_DO_REGISTRO)}>'
              'Registro</button>']
    if falhas:
        botoes.append('<button class="btn empurra" data-gesto="atualizacoes-tentar">'
                      'Tentar de novo</button>')
    if rodando:
        empurra = "" if falhas else " empurra"
        botoes.append(f'<button class="btn borda-vermelha{empurra}" '
                      f'data-gesto="atualizacoes-parar">'
                      'Parar</button>')
    return (f'<div class="tn-cx larga" role="dialog" aria-modal="true" aria-label="Atualizações">'
            f'<div class="tn-topo"><span class="tn-tit">Atualizações</span>'
            f'<button class="tn-x" data-gesto="atualizacoes-fechar"{_dica("Esconder")}>'
            f'&times;</button>'
            f'</div><div class="tn-corpo"><div class="and-total"><span class="rot">Total</span>'
            f'<span class="trilho"><span class="cheio" style="width:{pct}%"></span></span>'
            f'<span class="n">{feitas} de {de} · {pct}%</span>{erro}</div>'
            f'<div class="and-lista">{"".join(_linha_do_andamento(p) for p in pecas)}{linha_r}'
            f'</div></div><div class="tn-rod">{"".join(botoes)}</div></div>')


def _selo_da_grade(item: dict[str, Any]) -> str:
    estado = item.get("estado")
    if estado == "nova":
        return '<span class="selo nova"><span class="sg">↑</span>NOVA</span>'
    if estado == "em_dia":
        return '<span class="selo ok"><span class="sg">✓</span>EM DIA</span>'
    if estado == "fixa":
        return (f'<span class="selo nt"{_dica(DICA_DA_FIXA)}><span class="sg">&ndash;</span>'
                'FIXA</span>')
    return (f'<span class="selo nt"{_dica(item.get("dica", ""))}><span class="sg">&ndash;</span>'
            'SEM REDE</span>')


def grade_da_aba(conferencia: dict[str, Any]) -> str:
    """As peças da aba Sistema em três colunas, com a marca que vale com «Atualizar sozinho»."""
    itens = _ordenadas(conferencia.get("pecas") or [])
    linhas = []
    for item in itens:
        marcavel = item.get("volta", 1) == 1
        marca = (f'<input type="checkbox" class="at-marca" data-gesto="peca-da-atualizacao" '
                 f'data-v="{_e(item["id"])}"{" checked" if item.get("marcada") else ""}>'
                 if marcavel else '<input type="checkbox" class="at-marca" disabled>')
        fixa = " fixa" if item.get("estado") == "fixa" else ""
        linhas.append(f'<div class="saude{fixa}">{marca}{_selo_da_grade(item)}'
                      f'<span class="txt"{_dica(item.get("dica", ""))}><span>{_e(item.get("nome"))}'
                      f'</span></span><span class="ver"{_dica(_ver_inteira(item))}>{_ver(item)}'
                      '</span></div>')
    colunas, i = [], 0
    for n in COLUNAS_DA_GRADE:
        colunas.append(f'<div class="col-lista">{"".join(linhas[i:i + n])}</div>')
        i += n
    if i < len(linhas):
        colunas[-1] = colunas[-1][:-6] + "".join(linhas[i:]) + "</div>"
    return '<div class="risco"></div>'.join(colunas)


def quantas_novas(conferencia: dict[str, Any]) -> int:
    return sum(1 for i in _ordenadas(conferencia.get("pecas") or []) if i.get("estado") == "nova")


def js_da_caixa(corpo: str) -> str:
    return JS_DA_CAIXA % (json.dumps(CSS), json.dumps(corpo), json.dumps(ID_DA_CAIXA))
