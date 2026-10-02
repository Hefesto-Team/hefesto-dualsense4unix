"""O que o Flatpak deixa entrar no lançador — LANCADORES-ZERO-01 §5.4, 09/09/2026."""
from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

TODOS = "all"

ENTRADA = "input"

ENTRA = "entra"
NAO_ENTRA = "nao_entra"
NAO_INSTALADO = "nao_instalado"

_MARCA_DO_EXPORT = "flatpak/exports/"


def app_id_do_atalho(onde: str | Path | None) -> str:
    """O `app-id` do flatpak que publicou este `.desktop`, ou `""`."""
    if not onde:
        return ""
    texto = str(onde)
    if _MARCA_DO_EXPORT not in texto or not texto.endswith(".desktop"):
        return ""
    return Path(texto).stem


def _ini(caminho: Path) -> configparser.ConfigParser | None:
    """O arquivo lido, ou `None` — e NUNCA levanta."""
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    cfg.optionxform = str  # type: ignore[method-assign,assignment]
    try:
        cfg.read_string(caminho.read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error):
        return None
    return cfg


def _lista(cfg: configparser.ConfigParser | None, secao: str, chave: str
           ) -> list[str]:
    """Os itens de um valor `a;b;c;` do Flatpak, sem os vazios."""
    if cfg is None or not cfg.has_option(secao, chave):
        return []
    return [x.strip() for x in cfg.get(secao, chave).split(";") if x.strip()]


@dataclass(frozen=True)
class Permissao:
    """O que a caixa de UM aplicativo deixa entrar."""

    app_id: str
    estado: str = NAO_INSTALADO
    dispositivos: tuple[str, ...] = ()
    onde: Path | None = None
    porque: str = ""

    @property
    def entra(self) -> bool:
        return self.estado == ENTRA


def _raizes(lar: Path, raiz_sistema: Path | None) -> tuple[Path, Path]:
    return (lar / ".local/share/flatpak",
            Path("/var/lib/flatpak") if raiz_sistema is None else raiz_sistema)


def permissao_de(app_id: str, lar: Path | None = None,
                 raiz_sistema: Path | None = None) -> Permissao:
    """A caixa deste aplicativo: o que o pacote pede **mais** o que ela mudou."""
    lar = Path.home() if lar is None else lar
    usuario, sistema = _raizes(lar, raiz_sistema)
    meta = None
    onde: Path | None = None
    for raiz in (usuario, sistema):
        tentativa = raiz / "app" / app_id / "current/active/metadata"
        if tentativa.is_file():
            meta, onde = _ini(tentativa), tentativa
            break
    if meta is None:
        return Permissao(app_id, NAO_INSTALADO, (), None,
                         "não está instalado pelo Flatpak nesta máquina")
    tem = list(_lista(meta, "Context", "devices"))
    for arq in (sistema / "overrides/global", sistema / "overrides" / app_id,
                usuario / "overrides/global", usuario / "overrides" / app_id):
        if not arq.is_file():
            continue
        for item in _lista(_ini(arq), "Context", "devices"):
            if item.startswith("!"):
                tem = [x for x in tem if x != item[1:]]
            elif item not in tem:
                tem.append(item)
    if TODOS in tem:
        return Permissao(app_id, ENTRA, tuple(tem), onde,
                         "devices=all — a caixa abre todos os dispositivos")
    if ENTRADA in tem:
        return Permissao(app_id, ENTRA, tuple(tem), onde,
                         "devices=input — a caixa abre /dev/input, que é onde "
                         "o controle virtual aparece")
    return Permissao(app_id, NAO_ENTRA, tuple(tem), onde,
                     "devices não traz `all` nem `input` — nenhum controle "
                     "atravessa esta caixa")


def app_ids_instalados(atalhos: tuple[str, ...], lar: Path | None = None,
                       raiz_sistema: Path | None = None) -> tuple[str, ...]:
    """Os `app-id` desta lista que o Flatpak instalou NESTA máquina."""
    fora: list[str] = []
    for a in atalhos:
        if "." not in a or a in fora:
            continue
        if permissao_de(a, lar, raiz_sistema).estado != NAO_INSTALADO:
            fora.append(a)
    return tuple(fora)


def app_ids_do_cartao(atalhos: tuple[str, ...], onde: str | Path | None = None,
                      lar: Path | None = None,
                      raiz_sistema: Path | None = None) -> tuple[str, ...]:
    """As caixas que UM cartão da aba 07 representa."""
    fora = [x for x in (app_id_do_atalho(onde),) if x]
    for a in app_ids_instalados(atalhos, lar, raiz_sistema):
        if a not in fora:
            fora.append(a)
    return tuple(fora)


@dataclass(frozen=True)
class RespostaDoFlatpak:
    """O que o cartão «Flatpak» diz — a soma das caixas dos lançadores achados."""

    permissoes: tuple[Permissao, ...] = ()

    @property
    def dentro(self) -> tuple[Permissao, ...]:
        """As que o Flatpak instalou — as únicas sobre as quais há o que dizer."""
        return tuple(p for p in self.permissoes if p.estado != NAO_INSTALADO)

    @property
    def fechadas(self) -> tuple[Permissao, ...]:
        return tuple(p for p in self.dentro if not p.entra)

    @property
    def resumo(self) -> str:
        """A linha do cartão. Vazia quando não há lançador nenhum em caixa."""
        n = len(self.dentro)
        if not n:
            return ""
        fechadas = self.fechadas
        if not fechadas:
            return (f"{n} {'lançador' if n == 1 else 'lançadores'} por aqui, "
                    f"e o controle entra em {'todos' if n > 1 else 'ele'}")
        return (f"{n - len(fechadas)} de {n} deixam o controle entrar")


def resposta_do_flatpak(app_ids: tuple[str, ...], lar: Path | None = None,
                        raiz_sistema: Path | None = None) -> RespostaDoFlatpak:
    """As caixas dos lançadores que a aba ACHOU, na ordem em que ela os achou."""
    vistos: list[str] = []
    for a in app_ids:
        if a and a not in vistos:
            vistos.append(a)
    return RespostaDoFlatpak(tuple(permissao_de(a, lar, raiz_sistema)
                                   for a in vistos))
