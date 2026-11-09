"""O mapa das atualizações, as versões anteriores e o andamento.

O mapa nasce do botão «Atualizações» da aba Sistema (e sozinho, quando o prazo vence com peça
nova): as peças em cartões, agrupados pelo que há para baixar, marcáveis, com o «Atualizar» e as
versões anteriores no rodapé. A caixa nasce por cima de qualquer aba (``JS_DA_CAIXA``) e se repinta
inteira a cada mudança. Puro: recebe os dicionários do motor e devolve HTML.
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
GRUPOS_DO_MAPA = (("nova", "Para baixar"), ("revisar", "A revisar"), ("em_dia", "Em dia"),
                  ("fixa", "Com o Hefesto"), ("sem_rede", "Sem rede"))
ESTADOS_DO_MAPA = ("nova", "revisar", "em_dia", "fixa")
MARCAVEIS = ("nova", "em_dia", "fixa")
DICA_DO_SOZINHO = "Sem pergunta, só com o jogo fechado"
DICA_DO_PRAZO = "Prazo da conferência"
DICA_DO_REGISTRO = "O registro desta atualização"
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
.hef-atualiza .btn .n{font-family:'JetBrains Mono',monospace;font-size:12px}
.hef-atualiza .cadeado{display:inline-flex;align-items:center;justify-content:center;gap:9px;
  height:var(--h-acao,34px);white-space:nowrap;border-radius:999px;padding:0 16px 0 12px;width:auto;
  font:600 12.5px/1 'Space Grotesk',system-ui,sans-serif;cursor:pointer;
  border:1px solid var(--border-forte);background:var(--app-bg);color:var(--fg)}
.hef-atualiza .cadeado .p{width:10px;height:10px;border-radius:50%;flex:0 0 auto;
  background:var(--border-forte)}
.hef-atualiza .cadeado.ligada{border-color:var(--green);background:rgba(80,250,123,.09);
  color:var(--green)}
.hef-atualiza .cadeado.ligada .p{background:var(--green);box-shadow:0 0 6px var(--green)}
.hef-atualiza .prazo{display:inline-block;font-size:12.5px;color:var(--fg);white-space:nowrap}
.hef-atualiza .prazo > *{vertical-align:middle;margin-left:6px}
.hef-atualiza .prazo > :first-child{margin-left:0}
.hef-atualiza .prazo .pm{width:28px;height:28px;border-radius:6px;
  border:1px solid var(--linha,#53576f);background:var(--app-bg);color:var(--fg);
  font:600 14px/1 'JetBrains Mono',monospace;cursor:pointer}
.hef-atualiza .prazo .pm:hover{border-color:var(--comment)}
.hef-atualiza .prazo .dias{display:inline-block;min-width:26px;text-align:center;
  font-family:'JetBrains Mono',monospace;font-weight:500;color:var(--cyan)}
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
.hef-atualiza .tn-cx.mapa{width:min(1180px,calc(100vw - 32px));
  height:min(668px,calc(100vh - 32px));max-height:none;max-width:none}
.hef-atualiza .mapa .tn-topo{padding:10px 18px 9px;gap:16px;
  border-bottom:1px solid var(--border-sutil)}
.hef-atualiza .mapa .tn-tit{font-size:18px;font-weight:700;color:var(--pink)}
.hef-atualiza .mapa .btn.voltar{height:30px}
.hef-atualiza .mapa .at-ajuste{margin-left:auto;display:flex;align-items:center;gap:14px}
.hef-atualiza .mapa .at-ajuste .cadeado{height:30px}
.hef-atualiza .mapa .tn-corpo{padding:10px 18px;flex:1}
.hef-atualiza .mapa .tn-rod{padding:9px 18px 11px}
.hef-atualiza .mapa .tn-rod .empurra{flex:1}
.hef-atualiza .btn.apagado{opacity:.45;pointer-events:none}
.hef-atualiza .mp-corpo{display:flex;flex-direction:column;gap:6px}
.hef-atualiza .mp-g{display:flex;align-items:baseline;gap:8px;font-size:13px;font-weight:600;
  color:var(--green)}
.hef-atualiza .mp-g + .mp-grade{margin-bottom:2px}
.hef-atualiza .mp-g.nova{color:var(--purple)}
.hef-atualiza .mp-g.fixa,.hef-atualiza .mp-g.sem-rede{color:var(--comment)}
.hef-atualiza .mp-g .q{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:500;
  color:var(--texto-mudo)}
.hef-atualiza .mp-grade{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px 10px}
.hef-atualiza .mp-c{display:grid;grid-template-columns:34px minmax(0,1fr) 28px;align-items:center;
  gap:12px;height:52px;padding:0 10px 0 12px;border-radius:9px;
  border:1px solid var(--border-forte);background:var(--app-bg);color:var(--fg)}
.hef-atualiza label.mp-c{cursor:pointer}
.hef-atualiza label.mp-c:hover{border-color:var(--comment)}
.hef-atualiza .mp-i{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;color:var(--green);background:rgba(80,250,123,.10)}
.hef-atualiza .mp-i svg{width:19px;height:19px}
.hef-atualiza .mp-t{display:flex;flex-direction:column;gap:2px;min-width:0}
.hef-atualiza .mp-n{font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.hef-atualiza .mp-v{font-family:'JetBrains Mono',monospace;font-size:12px;
  color:var(--texto-suave);white-space:nowrap;overflow:hidden;display:flex;
  flex-flow:row-reverse wrap;justify-content:flex-end;height:16px;line-height:16px}
.hef-atualiza .mp-v .nv{order:-1;flex:0 1 auto;min-width:0;overflow:hidden;
  text-overflow:ellipsis}
.hef-atualiza .mp-v .par{flex:none}
.hef-atualiza .mp-v .seta{color:var(--purple);margin:0 5px}
.hef-atualiza .mp-c.nova .mp-v .nv{color:var(--fg);font-weight:500}
.hef-atualiza .mp-mx{width:28px;height:28px;display:flex;align-items:center;justify-content:center;
  cursor:pointer}
.hef-atualiza .mp-m{appearance:none;-webkit-appearance:none;width:18px;height:18px;margin:0;
  cursor:pointer;border-radius:5px;border:1.5px solid var(--linha,#53576f);background:var(--panel);
  display:grid;place-content:center}
.hef-atualiza .mp-m:checked{background:var(--pink);border-color:var(--pink)}
.hef-atualiza .mp-m:checked::after{content:"";width:9px;height:5px;margin-top:-2px;
  border-left:2px solid var(--app-bg);border-bottom:2px solid var(--app-bg);
  transform:rotate(-45deg)}
.hef-atualiza .mp-c.nova{border-color:var(--purple);
  background:color-mix(in srgb,var(--purple) 8%,var(--app-bg))}
.hef-atualiza .mp-c.nova .mp-i{color:var(--purple);
  background:color-mix(in srgb,var(--purple) 18%,transparent)}
.hef-atualiza .mp-c.nova:has(.mp-m:not(:checked)){border-color:var(--border-forte);
  background:var(--app-bg)}
.hef-atualiza .mp-c.nova:has(.mp-m:not(:checked)) .mp-i{color:var(--texto-mudo);
  background:var(--border-sutil)}
.hef-atualiza .mp-c.nova:has(.mp-m:not(:checked)) .mp-n,
.hef-atualiza .mp-c.nova:has(.mp-m:not(:checked)) .mp-v,
.hef-atualiza .mp-c.nova:has(.mp-m:not(:checked)) .mp-v .nv{color:var(--texto-mudo)}
.hef-atualiza:not(:has(.cadeado.ligada)) .mp-c:is(.em-dia,.fixa) .mp-mx{visibility:hidden}
.hef-atualiza:has(.cadeado.ligada) .mp-c:is(.em-dia,.fixa):has(.mp-m:not(:checked)) .mp-t{
  color:var(--texto-mudo)}
.hef-atualiza .mp-g.revisar{color:var(--orange)}
.hef-atualiza .mp-c.revisar{border-color:var(--orange);
  background:color-mix(in srgb,var(--orange) 7%,var(--app-bg))}
.hef-atualiza .mp-c.revisar .mp-i{color:var(--orange);
  background:color-mix(in srgb,var(--orange) 16%,transparent)}
.hef-atualiza .mp-c.revisar .mp-v .seta{color:var(--orange)}
.hef-atualiza .mp-s{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font:700 13px/1 'JetBrains Mono',monospace;background:var(--orange);
  color:var(--app-bg)}
.hef-atualiza .mp-c.fixa,.hef-atualiza .mp-c.sem-rede{border-style:dashed;
  background:transparent}
.hef-atualiza .mp-c.fixa .mp-i,.hef-atualiza .mp-c.sem-rede .mp-i{color:var(--comment);
  background:var(--border-sutil)}
.hef-atualiza .mp-c.fixa .mp-n,.hef-atualiza .mp-c.sem-rede .mp-n{color:var(--texto-suave)}
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
        return (f'<span class="par"><span class="de">{_e(versao_curta(de))}</span>'
                f'<span class="seta">→</span></span>'
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
    return estado if estado in ESTADOS_DO_MAPA else "sem_rede"


def _cartao(item: dict[str, Any]) -> str:
    grupo = _grupo_do_cartao(item)
    marcavel = item.get("volta", 1) == 1 and grupo in MARCAVEIS
    dica = " · ".join(x for x in (str(item.get("dica") or ""), _versao_inteira(item)) if x)
    inteiro = grupo == "nova" and marcavel
    marca = ""
    if marcavel:
        caixa = (f'<input type="checkbox" class="mp-m"{" checked" if item.get("marcada") else ""}'
                 f' data-gesto="peca-da-atualizacao" data-v="{_e(item["id"])}">')
        marca = f'<span class="mp-mx">{caixa}</span>' if inteiro else \
            f'<label class="mp-mx">{caixa}</label>'
    elif grupo == "revisar":
        marca = '<span class="mp-s">!</span>'
    etiqueta = "label" if inteiro else "div"
    return (f'<{etiqueta} class="mp-c {grupo.replace("_", "-")}"{_dica(dica)}>'
            f'<span class="mp-i">{_icone(str(item.get("id") or ""))}</span>'
            f'<span class="mp-t"><span class="mp-n">{_e(item.get("nome"))}</span>'
            f'<span class="mp-v">{_versao_a_vista(item)}</span></span>{marca}</{etiqueta}>')


def html_do_mapa(conferencia: dict[str, Any]) -> str:
    """As peças em cartões, por grupo: o que há para baixar primeiro."""
    itens = _ordenadas(conferencia.get("pecas") or [])
    blocos = []
    for chave, rotulo in GRUPOS_DO_MAPA:
        dentro = [i for i in itens if _grupo_do_cartao(i) == chave]
        if not dentro:
            continue
        blocos.append(f'<div class="mp-g {chave.replace("_", "-")}"><span>{rotulo}</span>'
                      f'<span class="q">{len(dentro)}</span></div>'
                      f'<div class="mp-grade">{"".join(_cartao(i) for i in dentro)}</div>')
    return f'<div class="mp-corpo">{"".join(blocos)}</div>'


def ids_para_atualizar(conferencia: dict[str, Any]) -> list[str]:
    return [str(i["id"]) for i in _ordenadas(conferencia.get("pecas") or [])
            if i.get("estado") == "nova" and i.get("marcada")]


def _ajuste(escolha: dict[str, Any]) -> str:
    sozinho = " ligada" if escolha.get("sozinho") else ""
    return (f'<span class="at-ajuste"><button class="cadeado{sozinho}" '
            f'data-gesto="atualizar-sozinho"'
            f'{_dica(DICA_DO_SOZINHO)}><span class="p"></span>Atualizar sozinho</button>'
            f'<span class="prazo"{_dica(DICA_DO_PRAZO)}><span>A cada</span>'
            f'<button class="pm" data-gesto="prazo-da-atualizacao" data-v="-1" '
            f'aria-label="Menos um dia">&minus;</button>'
            f'<span class="dias">{_e(escolha.get("dias", 7))}'
            f'</span><button class="pm" data-gesto="prazo-da-atualizacao" data-v="1" '
            f'aria-label="Mais um dia">+</button><span>dias</span></span></span>')


def html_da_pergunta(conferencia: dict[str, Any], escolha: dict[str, Any], *,
                     jogo_aberto: bool, nome_do_jogo: str = "") -> str:
    """O mapa das atualizações: o topo com o ajuste, os cartões e o rodapé."""
    n = len(ids_para_atualizar(conferencia))
    jogo = (f'<span>Jogo aberto:</span><span class="jogo">{_e(nome_do_jogo)}</span>'
            if nome_do_jogo else '<span>Jogo aberto</span>')
    pendente = (f'<div class="pendente">{jogo}<span>· espera</span></div>'
                if jogo_aberto else "")
    apagado = "" if n else " apagado"
    principal = (f'<button class="btn principal{apagado}" data-gesto="atualizacoes-atualizar">'
                 'Atualizar ao fechar o jogo</button>' if jogo_aberto else
                 f'<button class="btn principal{apagado}" data-gesto="atualizacoes-atualizar">'
                 f'Atualizar <span class="n">{n}</span></button>')
    return (f'<div class="tn-cx mapa" role="dialog" aria-modal="true" aria-label="Atualizações">'
            f'<div class="tn-topo"><button class="btn voltar" data-gesto="atualizacoes-fechar">'
            f'← Voltar</button><span class="tn-tit">Atualizações</span>{_ajuste(escolha)}'
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
        if ident not in pode_voltar or not isinstance(dado, dict) or not dado.get("anterior"):
            continue
        dica = _dica("No próximo início") if ident == "kernel" else ""
        linhas.append(
            f'<div class="vt-l"><span>{_e(dado.get("nome") or ident)}</span>'
            f'<span class="v"{_dica(str(dado.get("agora") or ""))}>'
            f'{_e(versao_curta(dado.get("agora")))}</span>'
            f'<span class="d">{_data(dado.get("desde"))}'
            f'</span><button class="btn amarelo-padrao" data-gesto="voltar-a-anterior" '
            f'data-v="{_e(ident)}"{dica}>Voltar a {_e(versao_curta(dado.get("anterior")))}'
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
        ver = (f'{_e(versao_curta(de))}<span class="seta">→</span>'
               f'<span class="nv">{_e(versao_curta(para))}</span>')
    else:
        ver = f'<span class="nv">{_e(versao_curta(para or de))}</span>'
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


def quantas_novas(conferencia: dict[str, Any]) -> int:
    return sum(1 for i in _ordenadas(conferencia.get("pecas") or []) if i.get("estado") == "nova")


def js_da_caixa(corpo: str) -> str:
    return JS_DA_CAIXA % (json.dumps(CSS), json.dumps(corpo), json.dumps(ID_DA_CAIXA))
