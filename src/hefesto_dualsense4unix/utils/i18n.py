"""Internacionalização (i18n) via gettext padrão freedesktop.

FEAT-I18N-INFRASTRUCTURE-01 (v3.4.0): baseline para tradução do
projeto. PT-BR continua sendo o source-language (todas as strings
hardcoded no código e no Glade estão em PT-BR), com EN como segundo
idioma oficial via catálogo `po/en.po` + `locale/en/LC_MESSAGES/
hefesto-dualsense4unix.mo`.

Como funciona:
- `_(msg)` é o wrapper canônico. Em qualquer ponto do código que tenha
  string user-facing, troque a string literal por `_("string")` para
  ela virar traduzível.
- `init_locale()` é chamado uma vez no boot da GUI (`app/main.py`) e
  da CLI (`cli/app.py`). Resolve o locale do sistema via env vars
  (`LANG`, `LC_ALL`, `LC_MESSAGES`) e instala o catálogo `.mo`.
- Glade (`main.glade`) é traduzido automaticamente via
  `Gtk.Builder.set_translation_domain("hefesto-dualsense4unix")` —
  qualquer label com `translatable="yes"` no .glade é resolvida via
  o mesmo catálogo gettext que o `_()` do Python.

Resolução de paths .mo (na ordem):
1. `$XDG_DATA_HOME/locale/` (usuário, override local).
2. `~/.local/share/locale/` (install.sh source-install).
3. `/usr/share/locale/` (`.deb` + RPM + PKGBUILD).
4. `/app/share/locale/` (Flatpak sandbox).
5. Diretório do wheel (`hefesto_dualsense4unix/locale/`) — fallback
   para `pip install`.

Fallback: se o `.mo` para o locale solicitado não for encontrado,
gettext retorna a string original (PT-BR) sem erro. Nunca quebra.
"""
from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Domínio gettext canônico do projeto. Tem que casar com o nome do .mo
#: (`hefesto-dualsense4unix.mo`), com `Gtk.Builder.set_translation_domain`
#: e com o `--default-domain` do `xgettext` no `scripts/i18n_extract.sh`.
TEXTDOMAIN = "hefesto-dualsense4unix"

_initialized = False


def _candidate_locale_dirs() -> list[Path]:
    """Lista paths onde procurar catálogos `.mo`, em ordem de preferência."""
    candidates: list[Path] = []

    # 1. XDG_DATA_HOME (override do usuário)
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        candidates.append(Path(xdg_data_home) / "locale")

    # 2. ~/.local/share/locale/ (install.sh source-install)
    candidates.append(Path.home() / ".local" / "share" / "locale")

    # 3. /usr/share/locale/ (.deb + RPM + PKGBUILD)
    candidates.append(Path("/usr/share/locale"))

    # 4. /app/share/locale/ (Flatpak sandbox)
    candidates.append(Path("/app/share/locale"))

    # 5. Diretório do wheel (`hefesto_dualsense4unix/locale/`) — fallback
    #    para quem instala via `pip install` sem rodar install.sh.
    pkg_locale = Path(__file__).resolve().parent.parent / "locale"
    candidates.append(pkg_locale)

    return candidates


def _find_locale_dir() -> Path | None:
    """Retorna o primeiro path que contém pelo menos 1 `.mo` do projeto."""
    for path in _candidate_locale_dirs():
        if not path.is_dir():
            continue
        # Verifica se existe pelo menos 1 idioma com nosso domínio.
        for lang_dir in path.iterdir():
            mo = lang_dir / "LC_MESSAGES" / f"{TEXTDOMAIN}.mo"
            if mo.is_file():
                return path
    return None


def init_locale() -> str | None:
    """Inicializa gettext + locale do sistema. Idempotente.

    Retorna o nome do locale efetivamente carregado (ex: `en_US.UTF-8`)
    ou `None` se nenhum catálogo foi encontrado (fallback PT-BR
    hardcoded).
    """
    global _initialized
    if _initialized:
        return locale.getlocale(locale.LC_MESSAGES)[0]

    # `setlocale("")` lê env vars (LANG, LC_ALL, LC_MESSAGES) e ajusta
    # o locale do processo. Defensivo: alguns ambientes têm
    # LANG="C.UTF-8" que não tem catálogos — gettext fará fallback OK.
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error as exc:
        logger.debug("i18n_setlocale_falhou", err=str(exc))

    locale_dir = _find_locale_dir()
    if locale_dir is None:
        logger.debug(
            "i18n_no_catalog_found",
            candidates=[str(p) for p in _candidate_locale_dirs()],
            hint="Mantendo strings hardcoded PT-BR (fallback gettext).",
        )
        _initialized = True
        return None

    # bindtextdomain ensina o gettext onde achar os .mo.
    # textdomain define o domínio default para `_()` sem qualificação.
    gettext.bindtextdomain(TEXTDOMAIN, str(locale_dir))
    gettext.textdomain(TEXTDOMAIN)

    # Glade usa o mesmo mecanismo via Gtk.Builder.set_translation_domain.
    # Documentamos aqui para reforçar o vínculo.

    active = locale.getlocale(locale.LC_MESSAGES)[0]
    logger.info(
        "i18n_initialized",
        locale=active or "C",
        locale_dir=str(locale_dir),
        domain=TEXTDOMAIN,
    )
    _initialized = True
    return active


def _(message: str) -> str:
    """Wrapper canônico para gettext.

    Uso:
        from hefesto_dualsense4unix.utils.i18n import _

        button.set_label(_("Aplicar"))
        logger.user_facing(_("Perfil ativado: %s") % name)

    Comportamento:
    - Se `init_locale()` foi chamado e o catálogo do locale ativo
      contém `message`, retorna a tradução.
    - Caso contrário, retorna `message` literal (fallback PT-BR).
    """
    if not _initialized:
        # Nunca chamado init_locale() — provavelmente teste isolado.
        # Devolve string original sem ativar gettext (zero overhead).
        return message
    return gettext.gettext(message)


__all__ = ["TEXTDOMAIN", "_", "init_locale"]
