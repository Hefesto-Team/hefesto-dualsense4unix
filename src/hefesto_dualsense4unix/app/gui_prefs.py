"""Utilitários para ler e escrever preferências da GUI em JSON.

Arquivo de estado: ~/.config/hefesto-dualsense4unix/gui_preferences.json
Tolerante a ausência do arquivo (retorna defaults).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# CHORE-CONFIG-MIGRATE-LEGACY-SHORT-PATH-01: usa o caminho XDG canônico
# (`~/.config/hefesto-dualsense4unix`) via `xdg_paths` — antes era hardcoded no
# caminho curto legado `~/.config/hefesto`, divergindo de perfis/sessão e
# deixando as preferências órfãs após reinstalar. A migração curto→longo
# (`utils.migrate_legacy_paths`) traz preferências antigas para cá.
_PREFS_NOME = "gui_preferences.json"


def _prefs_file() -> Path:
    """Caminho do arquivo de preferências, resolvido NA CHAMADA.

    LUZ-CEGA-01/E8 (25/08/2026) — era constante de módulo
    (``_CONFIG_DIR = xdg_paths.config_dir()``), e constante de módulo é
    avaliada na IMPORTAÇÃO. Sob a suíte isso vaza o ``$HOME`` REAL de quem
    roda: o ``tests/conftest.py`` isola ``XDG_CONFIG_HOME`` numa fixture de
    FUNÇÃO, que só corre DEPOIS da coleta — quando este módulo já congelou o
    caminho verdadeiro. Qualquer ``save_gui_prefs`` num teste escrevia em
    ``~/.config/hefesto-dualsense4unix/gui_preferences.json`` da máquina.

    É exatamente a classe de defeito que o CANARIO-FS-01 (05/08/2026)
    nomeia no próprio texto de reprovação — *"procure constante de módulo
    com Path.home() avaliada no import"* — e que aquele dia curou em
    ``storm_doctor._allowlist_path`` e ``EmulationActionsMixin._wp_dropin_dir``.
    Esta terceira passou. Em produção nada muda: ``config_dir()`` já resolve
    ``XDG_CONFIG_HOME`` a cada chamada.
    """
    return xdg_paths.config_dir() / _PREFS_NOME

_DEFAULTS: dict[str, Any] = {
    "advanced_editor": False,
    # `None` = ninguém corrigiu, e a detecção da sessão vale. Esta chave é o
    # que a aba Configurações grava quando a leitura de `XDG_CURRENT_DESKTOP`
    # erra — ver `app/ambiente.py`, que é o dono do valor e o único que o
    # valida. Ela mora AQUI e não em `maquina.json`: é preferência de janela,
    # e nada fora da janela a lê.
    "ambiente_corrigido": None,
    # AS TABELAS QUE ELA ARRASTA — ver o bloco `_TABELAS` no fim deste arquivo.
    # Vazio é o estado de quem nunca arrastou nem escolheu ordem nenhuma.
    "tabelas": {},
}


def _defaults() -> dict[str, Any]:
    """Uma cópia NOVA dos padrões, a cada chamada.

    `dict(_DEFAULTS)` era cópia RASA, e desde que `tabelas` virou um dicionário
    aninhado (11/09/2026) isso é uma armadilha: quem recebesse os padrões e
    mexesse no dicionário de dentro estaria mexendo na constante do módulo, e o
    estrago valeria para o processo inteiro. Nenhum chamador de hoje faz isso —
    e é exatamente por isso que a hora de fechar é agora, antes de o primeiro
    aparecer.
    """
    return {k: (dict(v) if isinstance(v, dict) else v)
            for k, v in _DEFAULTS.items()}


def load_gui_prefs() -> dict[str, Any]:
    """Carrega preferências da GUI.

    Retorna dict com defaults se o arquivo não existir ou estiver corrompido.
    """
    prefs_file = _prefs_file()
    if not prefs_file.exists():
        return _defaults()
    try:
        raw = prefs_file.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(raw)
        prefs = _defaults()
        prefs.update(data)
        return prefs
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("gui_prefs: falha ao carregar preferencias, usando defaults", erro=str(exc))
        return _defaults()


def save_gui_prefs(prefs: dict[str, Any]) -> None:
    """Persiste preferências da GUI em disco.

    Cria o diretório pai se necessário. Falha silenciosa com log de aviso.
    """
    try:
        prefs_file = _prefs_file()
        prefs_file.parent.mkdir(parents=True, exist_ok=True)
        prefs_file.write_text(
            json.dumps(prefs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("gui_prefs: falha ao salvar preferencias", erro=str(exc))


def set_pref(key: str, value: Any) -> None:
    """Atalho: carrega, atualiza uma chave e salva."""
    prefs = load_gui_prefs()
    prefs[key] = value
    save_gui_prefs(prefs)


# ---------------------------------------------------------------------------
# AS TABELAS QUE ELA ARRASTA — PERFIS-LIMPA-01, 11/09/2026.
#
# Ordem dela: *"essa tabela abaixo dele tem a largura configurável pelo user
# (quando o cursor muda e permite alterar a largura da coluna) e isso passa a
# ser lembrado no futuro."*
#
# POR QUE AQUI E NÃO NO `maquina.json`, e a resposta já estava escrita por quem
# separou os dois: *"o arquivo da janela é da JANELA"* (`utils/maquina.py`, a
# nota de `ordens_dispensadas`). Largura de coluna e ordem de listagem não
# afirmam nada sobre a mesa, o rádio ou o aparelho — elas são a janela dela,
# como o `ambiente_corrigido` que já mora aqui.
#
# UMA CHAVE, UM DICIONÁRIO: `tabelas` → tabela → `{larguras, ordem}`. Duas
# chaves de topo dariam dois lugares para o mesmo assunto, e é o que faz a
# próxima pessoa gravar num e ler do outro.
#
# A ORDEM VIAJA JUNTO DA LARGURA, e o preço está declarado na sprint: ela pediu
# memória para a largura, não para a ordem. É a mesma gravação e o mesmo gesto,
# e uma tabela que lembra a largura e esquece a ordem lembra pela metade. Se ela
# recusar, some a chave `ordem` daqui e nada mais.
_TABELAS = "tabelas"

#: O PISO DA COLUNA, em pixels. **Não é gosto: uma coluna arrastada a 3px some
#: e ela não tem onde pegar de novo para desfazer.** 48px é o que ainda mostra
#: a alça de arraste (24px de alvo, §3) mais folga para o cursor achar a divisa.
PISO_DA_COLUNA = 48

#: O TETO, pelo mesmo motivo pelo avesso: uma coluna arrastada além da largura
#: da janela empurra as irmãs para fora e a tabela deixa de caber.
TETO_DA_COLUNA = 900


def _tabelas() -> dict[str, Any]:
    bruto = load_gui_prefs().get(_TABELAS)
    return dict(bruto) if isinstance(bruto, dict) else {}


def larguras_da_tabela(tabela: str) -> dict[str, int]:
    """As larguras que ela deixou naquela tabela — `{coluna: px}`.

    Vazio é o estado honesto de quem nunca arrastou: a tabela abre com o que o
    CSS diz, e não com um número inventado aqui.
    """
    bruto = _tabelas().get(tabela) or {}
    larguras = bruto.get("larguras") if isinstance(bruto, dict) else None
    if not isinstance(larguras, dict):
        return {}
    limpas: dict[str, int] = {}
    for coluna, px in larguras.items():
        try:
            valor = int(px)
        except (TypeError, ValueError):
            continue
        limpas[str(coluna)] = max(PISO_DA_COLUNA, min(TETO_DA_COLUNA, valor))
    return limpas


def guardar_largura_de_coluna(tabela: str, coluna: str, px: int) -> int:
    """Grava a largura de UMA coluna e devolve o que foi realmente gravado.

    O RETORNO É O VALOR APARADO, e não o pedido: quem chama precisa dizer à tela
    o número que ficou, senão a coluna volta sozinha ao piso no próximo pintar e
    a tela mostra um número que o disco não tem.
    """
    valor = max(PISO_DA_COLUNA, min(TETO_DA_COLUNA, int(px)))
    prefs = load_gui_prefs()
    tabelas = dict(prefs.get(_TABELAS) or {})
    desta = dict(tabelas.get(tabela) or {})
    larguras = dict(desta.get("larguras") or {})
    larguras[str(coluna)] = valor
    desta["larguras"] = larguras
    tabelas[str(tabela)] = desta
    prefs[_TABELAS] = tabelas
    save_gui_prefs(prefs)
    return valor


def ordem_da_tabela(tabela: str) -> tuple[str, str]:
    """Por qual coluna aquela tabela está ordenada, e para onde.

    `("", "")` é *"ninguém escolheu"* — e é diferente de escolher a primeira
    coluna: sem escolha, a ordem é a que o produto monta (o ativo primeiro), e é
    ela que a tela mostrava antes de esta memória existir.
    """
    bruto = _tabelas().get(tabela) or {}
    ordem = bruto.get("ordem") if isinstance(bruto, dict) else None
    if not isinstance(ordem, dict):
        return ("", "")
    coluna = str(ordem.get("coluna") or "")
    sentido = str(ordem.get("sentido") or "")
    return (coluna, sentido if sentido in ("asc", "desc") else "asc")


def guardar_ordem_da_tabela(tabela: str, coluna: str, sentido: str) -> None:
    """Grava a coluna e o sentido. Coluna vazia APAGA a escolha."""
    prefs = load_gui_prefs()
    tabelas = dict(prefs.get(_TABELAS) or {})
    desta = dict(tabelas.get(tabela) or {})
    if not coluna:
        desta.pop("ordem", None)
    else:
        desta["ordem"] = {"coluna": str(coluna),
                          "sentido": "desc" if sentido == "desc" else "asc"}
    tabelas[str(tabela)] = desta
    prefs[_TABELAS] = tabelas
    save_gui_prefs(prefs)
