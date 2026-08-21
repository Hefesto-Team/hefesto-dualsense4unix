"""Fixtures compartilhadas entre testes unit e integration.

Além das fixtures, este arquivo hospeda a GUARDA-GI-REAL-01 — a resposta ao
defeito medido em 28/07: ``pytest.importorskip("gi")`` é DERROTADO por poluição
de ``sys.modules``. Vinte e um arquivos de teste plantam um ``gi`` falso (com
``Gtk.Box = object``) no nível de módulo; quem vem depois na ORDEM ALFABÉTICA
importa esse falso, o ``importorskip`` não pula, e centenas de testes de
interface reportam PASSED contra um GTK de mentira. Cobertura falsa é pior do
que cobertura ausente. Ver ``exigir_gi_real`` e ``pytest_collectstart`` abaixo.
"""

import contextlib
import fnmatch
import hashlib
import os
import shutil
import sys
import tempfile
import types
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# GUARDA-GI-REAL-01 — o `gi` do processo é o de verdade, ou é um stub?
# ---------------------------------------------------------------------------

#: Nomes de módulo que os stubs de teste plantam em ``sys.modules``.
_PREFIXO_GI = "gi"


def _e_modulo_gi(nome: str) -> bool:
    """True para ``gi`` e qualquer submódulo (``gi.repository.Gtk`` etc.)."""
    return nome == _PREFIXO_GI or nome.startswith(_PREFIXO_GI + ".")


def _gtk_e_real(gtk: Any) -> bool:
    """True quando ``gtk`` expõe widgets de VERDADE, não os do stub.

    O stub canônico dos testes faz ``Gtk.Box = object`` — passa em qualquer
    ``hasattr``, e é justamente por isso que ``importorskip`` não o pega. Aqui
    o critério é o que distingue os dois: no PyGObject real ``Gtk.Box`` é uma
    classe própria (``gi.overrides.Gtk.Box``), nunca o ``object`` embutido.
    """
    caixa = getattr(gtk, "Box", None)
    if caixa is None or caixa is object:
        return False
    if not isinstance(caixa, type):
        return False
    # `types.ModuleType` puro (o stub) nunca tem `ListStore` E `Box` reais ao
    # mesmo tempo; o real tem os dois.
    lista = getattr(gtk, "ListStore", None)
    return lista is not None and lista is not object


def gi_real_no_processo() -> bool:
    """True quando o ``gi`` JÁ CARREGADO neste processo é o PyGObject real.

    Devolve False tanto para "não há ``gi``" quanto para "há um stub plantado
    por outro arquivo de teste" — é esta segunda resposta que o
    ``pytest.importorskip("gi")`` erra.
    """
    modulo_gi = sys.modules.get(_PREFIXO_GI)
    if modulo_gi is None:
        return False
    # `types.ModuleType("gi")` nasce com `__spec__` None; o pacote real tem um.
    if getattr(modulo_gi, "__spec__", None) is None:
        return False
    gtk = sys.modules.get("gi.repository.Gtk")
    if gtk is None:
        # O `gi` é real e o Gtk ainda não foi carregado — nada a reprovar.
        return True
    return _gtk_e_real(gtk)


def gi_stub_no_processo() -> bool:
    """True quando há um ``gi`` carregado e ele é FALSO (stub de teste)."""
    return any(_e_modulo_gi(n) for n in sys.modules) and not gi_real_no_processo()


def _remover_gi_do_processo() -> list[str]:
    """Apaga todo ``gi*`` de ``sys.modules`` e devolve os nomes removidos."""
    removidos = [n for n in list(sys.modules) if _e_modulo_gi(n)]
    for nome in removidos:
        del sys.modules[nome]
    return removidos


#: Fotografia dos módulos ``gi*`` REAIS, mantida em dia enquanto o processo tem
#: o PyGObject de verdade carregado.
#:
#: Ela existe por uma razão medida: NÃO se desfaz um stub simplesmente apagando
#: o ``gi`` e deixando o próximo módulo reimportar. O PyGObject registra tipos
#: no GObject na primeira importação, e a segunda estoura
#: ``RuntimeError: Unable to register enum 'PyGLibUserDirectory'`` — na máquina
#: da mantenedora isso derrubou 66 testes e 39 coletas de uma vez. Devolver os
#: MESMOS objetos de módulo não reimporta nada e não registra nada de novo.
_FOTO_GI_REAL: dict[str, Any] = {}


def _atualizar_foto_gi_real() -> None:
    """Guarda os módulos ``gi*`` atuais — só chamar com o ``gi`` REAL no ar."""
    for nome in list(sys.modules):
        if _e_modulo_gi(nome):
            _FOTO_GI_REAL[nome] = sys.modules[nome]


def _restaurar_gi_real_da_foto() -> bool:
    """Troca o stub pelos módulos reais fotografados. False se não há foto."""
    if not _FOTO_GI_REAL:
        return False
    _remover_gi_do_processo()
    sys.modules.update(_FOTO_GI_REAL)
    return gi_real_no_processo()


def _sondar_gtk_do_ambiente() -> tuple[bool, bool]:
    """Pergunta a um SUBPROCESSO limpo o que o ambiente tem de GTK.

    Devolve ``(gi_real_disponivel, response_type_presente)``.

    Roda fora do processo de propósito: importar o Gtk aqui, no conftest
    (avaliado cedo, na coleta), competiria com a versão que outro teste já
    carregou — o repo mistura Gtk 3.0 (produção) e 4.0 (fixtures), e
    "Namespace already loaded" derruba a coleta inteira. O subprocesso não tem
    esse estado e responde só as duas perguntas que importam.
    """
    import subprocess

    codigo = (
        "import sys\n"
        "try:\n"
        "    import gi\n"
        "    try:\n"
        "        gi.require_version('Gtk', '3.0')\n"
        "    except Exception:\n"
        "        pass\n"
        "    from gi.repository import Gtk\n"
        "except Exception:\n"
        "    print('0 0')\n"
        "    sys.exit(0)\n"
        "caixa = getattr(Gtk, 'Box', None)\n"
        "lista = getattr(Gtk, 'ListStore', None)\n"
        "real = (\n"
        "    caixa is not None and caixa is not object and isinstance(caixa, type)\n"
        "    and lista is not None and lista is not object\n"
        ")\n"
        "print(('1' if real else '0'), ('1' if hasattr(Gtk, 'ResponseType') else '0'))\n"
    )
    try:
        r = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        return (False, False)
    saida = r.stdout.decode("utf-8", "replace").split()
    if r.returncode != 0 or len(saida) != 2:
        return (False, False)
    return (saida[0] == "1", saida[1] == "1")


#: Medido UMA vez, na importação do conftest (o subprocesso é barato).
GI_REAL_DISPONIVEL, _GTK_RESPONSE_TYPE_PRESENTE = _sondar_gtk_do_ambiente()

#: Quando ligado, "pular por falta de GTK real" vira REPROVAÇÃO. É o que o job
#: dedicado do CI (com `python3-gi` + typelibs + Xvfb) usa: lá, um pulo é um
#: defeito de ambiente disfarçado de sucesso, e o pulo silencioso é metade do
#: problema que esta guarda existe para curar.
EXIGE_GTK_REAL = os.environ.get("HEFESTO_EXIGE_GTK_REAL") == "1"

_MOTIVO_SEM_GI = (
    "GUARDA-GI-REAL-01: PyGObject real ausente (ou substituído por stub de "
    "teste). Instale python3-gi + gir1.2-gtk-3.0 para exercitar a interface."
)

#: Marker reusável: pula quando o GTK do ambiente não expõe os enums de widget.
skip_sem_gtk_response = pytest.mark.skipif(
    not _GTK_RESPONSE_TYPE_PRESENTE,
    reason="Gtk.ResponseType indisponível (GTK parcial — CI headless)",
)

#: Marker reusável: pula quando não há PyGObject REAL. Substitui, com critério
#: honesto, o ``pytest.importorskip("gi")`` — que aceita o stub.
skip_sem_gi_real = pytest.mark.skipif(not GI_REAL_DISPONIVEL, reason=_MOTIVO_SEM_GI)

#: Módulos que pularam por falta de GTK real, para o resumo alto no fim do run.
_MODULOS_PULADOS_SEM_GI: list[str] = []

#: Módulos cujo `gi` FALSO foi retirado antes da importação do módulo seguinte.
_MODULOS_DESPOLUIDOS: list[str] = []


def _carregar_gi_real() -> None:
    """Importa o PyGObject real (Gtk 3.0) no processo, em silêncio se não der."""
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        repositorio = __import__("gi.repository", fromlist=["Gtk"])
        _ = repositorio.Gtk
    except Exception:  # pragma: no cover — ambiente degradado ou sem GTK
        pass


def exigir_gi_real(motivo: str = "") -> None:
    """Guarda de nível de módulo: exige o PyGObject REAL, reprovando o stub.

    Use no lugar de ``pytest.importorskip("gi")`` em todo módulo de teste que
    só faz sentido contra o GTK de verdade. A diferença é o critério:

    - ``importorskip("gi")`` pergunta "``import gi`` funciona?" — e um stub
      plantado por OUTRO arquivo de teste responde que sim;
    - ``exigir_gi_real()`` pergunta "o ``Gtk`` deste processo tem widgets de
      verdade?" — e o stub (``Gtk.Box = object``) reprova.

    Quando há stub carregado mas o AMBIENTE tem PyGObject real, a função limpa
    o stub em vez de pular: quem mentiu foi o arquivo anterior, e a máquina de
    desenvolvimento não pode perder centenas de testes por causa disso.
    """
    if gi_real_no_processo():
        return

    if GI_REAL_DISPONIVEL:
        # Ambiente bom, processo envenenado: devolve os módulos reais (a foto)
        # ou, se ainda não há foto, importa o PyGObject pela primeira vez.
        if not _restaurar_gi_real_da_foto():
            _remover_gi_do_processo()
            _carregar_gi_real()
        if gi_real_no_processo():
            _atualizar_foto_gi_real()
            return

    texto = _MOTIVO_SEM_GI + (f" [{motivo}]" if motivo else "")
    _MODULOS_PULADOS_SEM_GI.append(motivo or "<módulo sem rótulo>")
    if EXIGE_GTK_REAL:
        pytest.fail(
            "HEFESTO_EXIGE_GTK_REAL=1 e o GTK real NÃO está disponível: " + texto,
            pytrace=False,
        )
    pytest.skip(texto, allow_module_level=True)


def instalar_stubs_gi(
    monkeypatch: pytest.MonkeyPatch,
    *,
    widgets: tuple[str, ...] = (),
) -> types.ModuleType:
    """Planta stubs de ``gi`` ISOLADOS, desfeitos ao fim do escopo do monkeypatch.

    Alternativa ao ``sys.modules["gi"] = ...`` cru: o ``monkeypatch.setitem``
    devolve ``sys.modules`` ao estado anterior no teardown, então a poluição
    não vaza para o arquivo seguinte. Devolve o módulo ``gi.repository.Gtk``
    plantado, para o chamador acrescentar o que faltar.
    """
    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    for nome in widgets:
        setattr(gtk_mod, nome, object)
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gi", gi_mod)
    monkeypatch.setitem(sys.modules, "gi.repository", repo_mod)
    monkeypatch.setitem(sys.modules, "gi.repository.Gtk", gtk_mod)
    return gtk_mod


def pytest_collectstart(collector: Any) -> None:
    """Impede que o ``gi`` FALSO de um arquivo vaze para o arquivo seguinte.

    Este é o coração da GUARDA-GI-REAL-01. A importação dos módulos de teste
    acontece toda na COLETA, antes de qualquer fixture rodar — por isso
    nenhuma fixture (nem ``monkeypatch``) chega a tempo de desfazer o plantio
    antes do próximo arquivo ser importado. Este hook chega: ele roda logo
    antes de cada módulo ser importado.

    Regra: se o ``gi`` carregado for REAL, não se mexe (é o estado desejado) e
    a fotografia dos módulos reais fica em dia. Se for um STUB, ele sai — pela
    fotografia, quando existe (máquina com GTK: o módulo seguinte recebe o
    PyGObject de verdade, sem reimportar nada), ou apagado (CI sem GTK: o
    módulo seguinte decide sozinho — importa, planta o próprio stub, ou pula).
    O que ele NÃO faz mais é herdar a mentira de quem veio antes por acaso da
    ordem alfabética.
    """
    if not isinstance(collector, pytest.Module):
        return
    if gi_real_no_processo():
        _atualizar_foto_gi_real()
        return
    if not gi_stub_no_processo():
        return
    if _restaurar_gi_real_da_foto():
        _MODULOS_DESPOLUIDOS.append(str(getattr(collector, "nodeid", collector)))
        return
    if _remover_gi_do_processo():
        _MODULOS_DESPOLUIDOS.append(str(getattr(collector, "nodeid", collector)))


def pytest_report_header(config: Any) -> str:
    """Diz, no cabeçalho do run, contra QUAL GTK a suíte vai rodar."""
    estado = "REAL (python3-gi + typelibs)" if GI_REAL_DISPONIVEL else "AUSENTE"
    extra = " | HEFESTO_EXIGE_GTK_REAL=1 (pulo vira reprovação)" if EXIGE_GTK_REAL else ""
    return f"guarda-gi-real-01: PyGObject {estado}{extra}"


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    """Torna VISÍVEL o pulo por falta de GTK — o pulo calado é parte do defeito."""
    escrever = terminalreporter.write_line
    if _MODULOS_PULADOS_SEM_GI:
        escrever("")
        escrever(
            "GUARDA-GI-REAL-01: "
            f"{len(_MODULOS_PULADOS_SEM_GI)} módulo(s) de interface PULARAM por "
            "falta de PyGObject real:",
            bold=True,
        )
        for nome in _MODULOS_PULADOS_SEM_GI:
            escrever(f"  - {nome}")
        escrever(
            "  Isto NÃO é cobertura. Instale python3-gi + gir1.2-gtk-3.0 "
            "para exercitar a interface."
        )
    if _MODULOS_DESPOLUIDOS:
        escrever("")
        escrever(
            "GUARDA-GI-REAL-01: stub de `gi` retirado antes de "
            f"{len(_MODULOS_DESPOLUIDOS)} módulo(s) — a poluição de sys.modules "
            "NÃO vazou entre arquivos.",
            bold=True,
        )


# ---------------------------------------------------------------------------
# CANARIO-FS-01 — a suíte escreveu no ~/.config DELA?
# ---------------------------------------------------------------------------
# O PORQUÊ, medido em 04/08/2026: os perfis dela foram encontrados corrompidos
# e a pergunta que ficou sem resposta foi "como sabemos se algum TESTE corrompeu
# algo?". A fixture `_hefesto_fake_env` isola os diretórios XDG — mas NÃO isola
# o ``HOME``, e há constantes de módulo avaliadas na IMPORTAÇÃO que apontam para
# arquivos reais dela por ``Path.home()``:
#
#   - `integrations/storm_doctor.py` (_ALLOWLIST_PATH, leitura);
#   - `app/actions/emulation_actions.py` (_WP_DROPIN_DIR, e este é dir de
#     ESCRITA em produção — o toggle do microfone cria e apaga drop-ins ali).
#
# Constante de módulo é avaliada ANTES de qualquer monkeypatch de ``HOME``, então
# nenhuma fixture consegue desviá-la depois.
#
# ATUALIZAÇÃO 05/08/2026 (decisão dela: *"preciso que as constantes apontem
# pros arquivos reais"*): as DUAS viraram função — `storm_doctor._allowlist_path`
# e `EmulationActionsMixin._wp_dropin_dir`. `Path.home()` dentro de função lê o
# ``HOME`` na hora da chamada, então o isolamento da suíte volta a valer e o
# comportamento em produção não muda. O canário CONTINUA, e não por desconfiança
# destas duas: ele cobre o que ninguém mapeou — subprocessos, `systemctl`,
# `uinput` e a próxima constante que alguém escrever sem pensar nisso.
#
# O canário fotografa (mtime_ns, tamanho, sha256) dos diretórios de verdade no
# início e no fim da sessão e REPROVA listando o que mudou. O hash não é zelo:
# a primeira versão comparava só (mtime_ns, size) e acusou 15 arquivos `.lock`
# na estreia — tocados pelo daemon e pela janela DELA, vivos ao lado da suíte.
# Um portão que grita no primeiro dia é um portão que alguém desliga no segundo.
#
# Isto não é hipótese: é medição. Se a suíte não escreve nada, o canário é
# invisível; se escreve, ele diz exatamente qual arquivo.

#: Diretórios REAIS que a suíte não pode tocar. Relativos ao ``HOME``.
_CANARIO_ALVOS: tuple[str, ...] = (
    ".config/hefesto-dualsense4unix",
    ".config/wireplumber",
    ".local/share/hefesto-dualsense4unix",
)

#: Árvores REAIS que a suíte também não devia mexer — mas onde um delta quase
#: nunca é escrita da suíte, e sim a **daemon VIVA dela reagindo à suíte**.
#: MEDIDO em 07/08/2026, com retrato do disco antes e depois de uma suíte
#: inteira: os quatro `launch_env/*.env` foram REGRAVADOS às 16:19:38, dentro
#: da janela da suíte, pelo daemon dela (pid 2870305, `launch_env_materializado`
#: no journal), 20 s depois da primeira rajada de teclados uinput que a suíte
#: cria — e o próprio daemon nomeia o mecanismo duas linhas adiante:
#: `backend_hotplug_reconcile trigger=input_dir_change`. A suíte não escreveu:
#: ela mexeu em `/dev/input`, e quem escreveu foi o daemon.
#:
#: Por isso AVISO e não portão. Reprovar aqui seria um alarme que fica vermelho
#: na máquina dela e verde na CI — exatamente o portão que se aprende a
#: desligar (é a lição do DIV-11, os 15 `.lock` da estreia do canário). O que
#: faltava era ENXERGAR: esta árvore estava fora de qualquer instrumento.
_CANARIO_ALVOS_AVISO: tuple[str, ...] = (".local/state/hefesto-dualsense4unix",)

#: Escotilha de saída, para quem PRECISA rodar a suíte contra o HOME real
#: (nunca deveria ser preciso — existe para não obrigar ninguém a comentar
#: código quando o daemon está de pé e mexendo no session.json ao lado).
#: Desliga as duas listas: a que reprova e a que só avisa.
_CANARIO_DESLIGADO_ENV = "HEFESTO_SEM_CANARIO_FS"

#: Fotografia do início da sessão: {caminho: (mtime_ns, tamanho, resumo)}.
_CANARIO_FOTO_INICIAL: dict[str, tuple[int, int, str]] = {}

#: A mesma coisa, para as árvores de AVISO (`_CANARIO_ALVOS_AVISO`).
_CANARIO_FOTO_AVISO: dict[str, tuple[int, int, str]] = {}

#: True só depois que a foto inicial foi tirada. Sem este selo, uma sessão que
#: começou com o canário desligado e terminou com ele ligado compararia contra
#: um dicionário vazio e acusaria TODO arquivo do ``$HOME`` de ter nascido
#: durante a suíte — o alarme mais falso que existe.
_CANARIO_ARMADO = False

#: Acima disto o arquivo não é resumido (só mtime+tamanho). Nada nos diretórios
#: vigiados chega perto — medido em 05/08: 93 arquivos, 356 KB no total; a
#: árvore de aviso somava 60 KB em 07/08.
_CANARIO_LIMITE_RESUMO = 4 * 1024 * 1024

#: Teto de linhas do relato de AVISO — ele não decide nada, e uma lista longa
#: só ensina a pular o bloco inteiro.
_CANARIO_LIMITE_AVISO = 10


def _canario_ligado() -> bool:
    return os.environ.get(_CANARIO_DESLIGADO_ENV) != "1"


def _canario_raizes() -> list[Path]:
    """Os alvos resolvidos contra o ``HOME`` REAL do processo.

    Lido de ``os.environ`` no momento da chamada de propósito: se um teste
    trocar o ``HOME``, as duas fotos ainda comparam a MESMA árvore, porque os
    dois hooks rodam fora de qualquer fixture.
    """
    lar = Path(os.path.expanduser("~"))
    return [lar / alvo for alvo in _CANARIO_ALVOS]


def _canario_raizes_de_aviso() -> list[Path]:
    """As árvores que só AVISAM, resolvidas contra o ``HOME`` VIVO."""
    lar = Path(os.path.expanduser("~"))
    return [lar / alvo for alvo in _CANARIO_ALVOS_AVISO]


def _resumo_do_arquivo(caminho: Path, tamanho: int) -> str:
    """sha256 do conteúdo — vazio para diretórios, ilegíveis e arquivos enormes.

    O resumo existe por uma medição de 05/08: com o daemon e a janela DELA de
    pé ao lado da suíte, os `*.json.lock` do diretório de perfis mudam de mtime
    a cada poucos segundos (o `filelock` toca o arquivo a cada aquisição). Um
    canário que reprovasse por mtime acusaria a suíte do que o daemon fez, e
    seria desligado na primeira semana. Conteúdo não mente: comparar o resumo
    reprova toda ESCRITA de verdade e ignora o vaivém dos locks.
    """
    if tamanho > _CANARIO_LIMITE_RESUMO:
        return ""
    try:
        return hashlib.sha256(caminho.read_bytes()).hexdigest()
    except OSError:
        return ""


def _fotografar_arvore(raiz: Path) -> dict[str, tuple[int, int, str]]:
    """{caminho: (mtime_ns, tamanho, resumo)} sob `raiz`. Ausente = dict vazio.

    Diretórios entram na foto para que um subdiretório novo (ou sumido) apareça
    como delta. Erros de permissão são pulados em silêncio: o canário mede o que
    consegue ver, e ver menos nunca pode derrubar a suíte por si só.
    """
    foto: dict[str, tuple[int, int, str]] = {}
    if not raiz.exists():
        return foto
    for caminho in [raiz, *raiz.rglob("*")]:
        try:
            st = caminho.stat()
            e_arquivo = caminho.is_file()
        except OSError:
            continue
        resumo = _resumo_do_arquivo(caminho, st.st_size) if e_arquivo else ""
        foto[str(caminho)] = (st.st_mtime_ns, st.st_size, resumo)
    return foto


def _fotografar_tudo() -> dict[str, tuple[int, int, str]]:
    foto: dict[str, tuple[int, int, str]] = {}
    for raiz in _canario_raizes():
        foto.update(_fotografar_arvore(raiz))
    return foto


def _fotografar_tudo_de_aviso() -> dict[str, tuple[int, int, str]]:
    foto: dict[str, tuple[int, int, str]] = {}
    for raiz in _canario_raizes_de_aviso():
        foto.update(_fotografar_arvore(raiz))
    return foto


def _deltas_do_canario(
    antes: dict[str, tuple[int, int, str]], depois: dict[str, tuple[int, int, str]]
) -> list[str]:
    """Lista legível do que mudou entre as duas fotos (vazia = nada mudou).

    Delta de arquivo é MUDANÇA DE CONTEÚDO (tamanho ou resumo) — mtime sozinho
    não conta, pelo motivo medido em `_resumo_do_arquivo`.
    """
    deltas: list[str] = []
    deltas.extend(f"CRIADO   {c}" for c in sorted(set(depois) - set(antes)))
    deltas.extend(f"APAGADO  {c}" for c in sorted(set(antes) - set(depois)))
    for caminho in sorted(set(antes) & set(depois)):
        (_mt_a, tam_a, resumo_a) = antes[caminho]
        (_mt_d, tam_d, resumo_d) = depois[caminho]
        if (tam_a, resumo_a) == (tam_d, resumo_d):
            continue
        detalhe = f"tamanho {tam_a}->{tam_d}" if tam_a != tam_d else "conteúdo"
        deltas.append(f"MUDADO   {caminho} ({detalhe})")
    return deltas


# ---------------------------------------------------------------------------
# BERCO-DE-TMP-01 — a suíte devolve o `/tmp` como encontrou
# ---------------------------------------------------------------------------
# O PORQUÊ, MEDIDO em 07/08/2026 (retrato do disco antes e depois de uma suíte
# inteira, 7619 passed em 232 s): o CANARIO-FS-01 acima vigia três árvores do
# ``$HOME`` e ficou CALADO — a suíte não escreveu em nenhuma. Mas ela deixou
# **16 entradas novas em `/tmp`**, que nenhum instrumento desta casa olhava:
#
#   9  `tmp<8>/`  ....... `tempfile.mkdtemp()` SEM limpeza, nos dois arquivos
#                         de teste de migração de perfil (7 + 2 chamadas);
#   6  `tmp.<10>`  ...... `mktemp` de shell, dentro de script sob teste;
#   1  `pulse-<12>/`  ... a libpulse criando o runtime dir dela.
#
# E o acumulado no dia da medição: **906** diretórios `tmp<8>`, dos quais 892
# ainda continham os arquivos que só os dois testes de migração escrevem
# (`.coop_default_on_migrated`, `.flavor_xbox_migrated`, `quebrado.json`…), mais
# 99 `pulse-*` e 3 `hefesto-arvore-congelada-*` que o `atexit` não alcançou
# porque a sessão foi morta. Ninguém limpou porque ninguém sabia.
#
# A CURA que não depende de alguém lembrar: **o `/tmp` da sessão não é o `/tmp`
# da máquina**. No `pytest_sessionstart` a suíte cria um BERÇO
# (``/tmp/hefesto-berco-<pid>``) e aponta `tempfile.tempdir` e `TMPDIR`/`TMP`/
# `TEMP` para ele. Tudo que nascer de `tempfile` (Python), de `mktemp` (shell,
# nos scripts sob teste) ou de qualquer biblioteca que respeite `TMPDIR`
# (libpulse) nasce DENTRO do berço; no fim da sessão o berço inteiro sai.
#
# O CRITÉRIO DE "ISTO É LIXO DE TESTE" É POSITIVO, e é o ponto do desenho:
# não é *"não reconheço este arquivo, então apago"* — é *"este diretório foi
# aberto por ESTA sessão de pytest, com ESTE pid no nome, e tudo que está
# dentro nasceu depois disso"*. Nada fora do berço é tocado, nunca, por
# nenhum caminho de código daqui.
#
# O que fica DE FORA do berço, de propósito:
#
#   - **o `basetemp` do pytest** (`/tmp/pytest-of-<user>/pytest-N`). Ele é
#     resolvido À FORÇA antes do desvio (`_fixar_basetemp_do_pytest`) por dois
#     motivos medidos: (a) o pytest já tem retenção própria (guarda as 3
#     últimas execuções, que é o que se olha quando um teste cai), e (b) o
#     `sun_path` de um `AF_UNIX` tem ~108 bytes — empurrar todo `tmp_path` para
#     dentro do berço somaria 27 bytes a caminhos que já batem em 95;
#   - **o `$HOME` dela.** Este mecanismo NÃO restaura nada em `$HOME`, e isso é
#     decisão, não esquecimento: a suíte não é a única a escrever ali (o daemon
#     e a janela DELA estão vivos ao lado), e "devolver ao estado anterior" um
#     arquivo que a daemon dela acabou de gravar é destruir trabalho real.
#     Para o `$HOME` o desenho continua sendo prevenir e DETECTAR — o
#     CANARIO-FS-01 acima.

#: Prefixo do berço. O nome carrega o pid da sessão: é ele que torna o critério
#: de varredura POSITIVO (nasceu desta sessão) em vez de negativo.
_BERCO_PREFIXO = "hefesto-berco-"

#: Escotilha, mesma lógica do canário: quem PRECISA inspecionar o que a suíte
#: deixou em `/tmp` desliga o desvio em vez de comentar código.
_BERCO_DESLIGADO_ENV = "HEFESTO_SEM_BERCO_TMP"

#: No máximo um elemento — o berço desta sessão. Lista para poder ser preenchida
#: dentro do hook sem `global`.
_BERCO: list[Path] = []

#: O `/tmp` de VERDADE, capturado ANTES do desvio.
_TMP_REAL: list[Path] = []

#: As variáveis de ambiente que decidem onde nasce um temporário — as três,
#: porque o `mktemp` de shell e a `tempfile` do Python não olham as mesmas.
_VARS_DE_TMP = ("TMPDIR", "TMP", "TEMP")

#: O valor que cada uma tinha ANTES do desvio (None = não existia), mais o
#: `tempfile.tempdir` sob a chave `None`. A varredura DEVOLVE, em vez de apagar:
#: quem chama o pytest de dentro de outro processo pode ter um `TMPDIR` próprio,
#: e ele não é nosso para jogar fora.
_TMP_ENV_ANTES: dict[str | None, str | None] = {}

#: `id()` da Session REAL desta execução, e ele não é zelo — é defeito medido em
#: 07/08/2026, na primeira integração deste berço. Nove testes do
#: `test_conftest_canario_fs.py` CHAMAM `pytest_sessionfinish` com uma Session
#: de mentira, de propósito, para provar que o canário reprova. Sem esta guarda,
#: a primeira dessas chamadas varria o berço da sessão VIVA no meio dela e
#: devolvia `tempfile.tempdir` para o `/tmp` real — a suíte voltava calada ao
#: comportamento antigo, e a única pista era um punhado de testes pulando.
_SESSAO_REAL: list[int] = []

#: Nomes de primeiro nível do `/tmp` real no início da sessão, para o aviso de
#: "nasceu FORA do berço" (caminho fixo escrito à mão num teste, por exemplo).
_TMP_ANTES: set[str] = set()

#: Teto de nomes listados nos relatos — nenhum deles é portão, e uma lista de
#: trezentas linhas no fim da suíte é uma lista que ninguém lê.
_BERCO_LIMITE_RELATO = 8


def _berco_ligado() -> bool:
    return os.environ.get(_BERCO_DESLIGADO_ENV) != "1"


def berco() -> Path | None:
    """O berço desta sessão, ou None quando o desvio não está armado."""
    return _BERCO[0] if _BERCO else None


def _pid_vivo(pid: int) -> bool:
    """True quando existe processo com este pid.

    ``PermissionError`` conta como VIVO: é processo de outro usuário, e a
    dúvida sempre se resolve para "não mexa".
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:  # pragma: no cover — pid inválido não chega aqui
        return True
    return True


def _pid_do_berco(nome: str) -> int | None:
    """O pid gravado no nome do berço, ou None quando o nome NÃO é de berço.

    Deliberadamente estrito: o sufixo tem de ser dígito puro. Um
    ``hefesto-berco-de-outra-coisa`` devolve None e nunca vira alvo.
    """
    if not nome.startswith(_BERCO_PREFIXO):
        return None
    resto = nome[len(_BERCO_PREFIXO) :]
    if not resto.isdigit():
        return None
    return int(resto)


def _bercos_orfaos(raiz: Path) -> list[Path]:
    """Berços de sessões MORTAS sob `raiz`, do mais antigo para o mais novo.

    Critério, todo ele positivo: o nome tem o prefixo do berço, o sufixo é um
    pid, é diretório, e esse pid NÃO está vivo. Sessão viva (inclusive a nossa)
    nunca entra na lista.
    """
    orfaos: list[Path] = []
    try:
        entradas = sorted(raiz.iterdir())
    except OSError:
        return orfaos
    for entrada in entradas:
        pid = _pid_do_berco(entrada.name)
        if pid is None or not entrada.is_dir() or entrada.is_symlink():
            continue
        if _pid_vivo(pid):
            continue
        orfaos.append(entrada)
    return orfaos


def _armar_berco(session: Any) -> None:
    """Cria o berço e desvia `tempfile` + `TMPDIR` para dentro dele."""
    if not _berco_ligado() or _BERCO:
        return
    _fixar_basetemp_do_pytest(session)
    raiz = Path(tempfile.gettempdir())
    _TMP_REAL.append(raiz)
    with contextlib.suppress(OSError):
        _TMP_ANTES.update(os.listdir(raiz))
    # Varre berços de sessões mortas ANTES de criar o nosso: uma sessão morta
    # (kill, queda de energia) não roda `sessionfinish`, e sem esta linha o
    # berço dela ficaria para sempre.
    for orfao in _bercos_orfaos(raiz):
        shutil.rmtree(orfao, ignore_errors=True)
    destino = raiz / f"{_BERCO_PREFIXO}{os.getpid()}"
    # Se já existe, é berço de uma sessão morta cujo pid o sistema reciclou
    # para nós — não pode ser de sessão viva, porque a sessão viva com este pid
    # somos nós.
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
    try:
        destino.mkdir(mode=0o700)
    except OSError:  # pragma: no cover — /tmp sem escrita derruba a suíte antes
        return
    _BERCO.append(destino)
    _SESSAO_REAL.append(id(session))
    _TMP_ENV_ANTES[None] = tempfile.tempdir
    tempfile.tempdir = str(destino)
    for var in _VARS_DE_TMP:
        _TMP_ENV_ANTES[var] = os.environ.get(var)
        os.environ[var] = str(destino)


def _fixar_basetemp_do_pytest(session: Any) -> None:
    """Resolve (e cacheia) o `basetemp` do pytest ANTES do desvio do `TMPDIR`.

    O `TempPathFactory` guarda o resultado em `self._basetemp` na primeira
    chamada; forçando-a aqui, `tmp_path` continua morando no `/tmp` real, com a
    retenção das 3 últimas execuções que o pytest já faz. Toda esta função é
    best-effort: se um pytest futuro mudar o atributo privado, o berço
    simplesmente passa a englobar o `basetemp` — e nada quebra.
    """
    fabrica = getattr(getattr(session, "config", None), "_tmp_path_factory", None)
    if fabrica is None:  # pragma: no cover — pytest sempre publica a fábrica
        return
    with contextlib.suppress(Exception):
        fabrica.getbasetemp()


def _nascidos_fora_do_berco() -> list[str]:
    """Nomes de primeiro nível que apareceram no `/tmp` REAL durante a sessão.

    É AVISO, nunca portão, e o motivo está escrito no relato: a máquina dela
    está viva, e o navegador, o PipeWire e os screenshots dela também escrevem
    em `/tmp`. O que este aviso pega de graça é a classe que o berço não
    alcança — caminho FIXO escrito à mão dentro de um teste, que ignora
    `TMPDIR` por construção (foi assim que `hefesto_teste_pactl_chamadas.txt`
    apareceu na medição de 07/08).
    """
    if not _TMP_REAL:
        return []
    nosso = berco()
    try:
        agora = set(os.listdir(_TMP_REAL[0]))
    except OSError:  # pragma: no cover
        return []
    novos = agora - _TMP_ANTES
    if nosso is not None:
        novos.discard(nosso.name)
    return sorted(novos)


def _varrer_berco(session: Any, exitstatus: int) -> None:
    """Fim de sessão: o berço inteiro sai, e o que havia nele é relatado.

    Só a Session que ARMOU o berço pode varrê-lo — ver `_SESSAO_REAL`. Uma
    Session de mentira (teste que chama o hook direto, para provar um portão)
    é ignorada aqui, e não no chamador: quem tem de saber quem é o dono do
    berço é o berço.
    """
    nosso = berco()
    if nosso is None:
        return
    if _SESSAO_REAL and id(session) not in _SESSAO_REAL:
        return
    try:
        restos = sorted(p.name for p in nosso.iterdir())
    except OSError:  # pragma: no cover
        restos = []

    if exitstatus != 0 and restos:
        # Sessão vermelha: o que a suíte deixou pode ser prova. Guardar custa
        # um diretório e a próxima sessão o varre pelo pid morto.
        _escrever_no_terminal(session, [
            "",
            f"BERCO-DE-TMP-01: sessão vermelha — o berço FICA, com {len(restos)} "
            f"entrada(s): {nosso}",
        ])
    else:
        shutil.rmtree(nosso, ignore_errors=True)
        if restos:
            mostrados = restos[:_BERCO_LIMITE_RELATO]
            restam = len(restos) - len(mostrados)
            cauda = f" (+{restam})" if restam > 0 else ""
            _escrever_no_terminal(session, [
                "",
                f"BERCO-DE-TMP-01: a suíte deixaria {len(restos)} entrada(s) em "
                f"/tmp; nasceram no berço e saíram com ele: "
                f"{', '.join(mostrados)}{cauda}",
            ])

    _BERCO.clear()
    tempfile.tempdir = _TMP_ENV_ANTES.get(None)
    for var, valor in _TMP_ENV_ANTES.items():
        if var is None:
            continue
        if valor is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = valor
    _TMP_ENV_ANTES.clear()

    fora = _nascidos_fora_do_berco()
    if fora:
        mostrados = fora[:_BERCO_LIMITE_RELATO]
        restam = len(fora) - len(mostrados)
        cauda = f" (+{restam})" if restam > 0 else ""
        _escrever_no_terminal(session, [
            f"BERCO-DE-TMP-01 (aviso, não é portão): apareceram em "
            f"{_TMP_REAL[0]} durante a sessão, FORA do berço: "
            f"{', '.join(mostrados)}{cauda}",
            "  A máquina dela também escreve em /tmp — mas se algum destes tem "
            "cara de teste,",
            "  é caminho FIXO escrito à mão num teste, e caminho fixo ignora o "
            "TMPDIR do berço.",
        ])


def pytest_sessionstart(session: Any) -> None:
    """CANARIO-FS-01: primeira fotografia dos diretórios REAIS da usuária.

    E BERCO-DE-TMP-01: a partir daqui, todo temporário desta sessão nasce
    dentro de um diretório que só esta sessão conhece.
    """
    global _CANARIO_ARMADO
    _armar_berco(session)
    if not _canario_ligado():
        return
    _CANARIO_FOTO_INICIAL.update(_fotografar_tudo())
    _CANARIO_FOTO_AVISO.update(_fotografar_tudo_de_aviso())
    _CANARIO_ARMADO = True


def _escrever_no_terminal(session: Any, linhas: list[str]) -> None:
    """Imprime pelo terminalreporter quando ele existe; senão, no stdout."""
    relator = None
    config = getattr(session, "config", None)
    gerenciador = getattr(config, "pluginmanager", None)
    if gerenciador is not None:
        relator = gerenciador.get_plugin("terminalreporter")
    for linha in linhas:
        if relator is not None:
            relator.write_line(linha)
        else:  # pragma: no cover — pytest sempre tem terminalreporter
            print(linha)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Sob ``HEFESTO_EXIGE_GTK_REAL=1``, pulo por falta de GTK reprova o run.

    E, sempre, o CANARIO-FS-01: se a suíte mexeu em qualquer arquivo dos
    diretórios REAIS da usuária, o run REPROVA com a lista do que mudou. Um
    teste hermético não deixa rastro nenhum em ``$HOME``.

    Por último, e SEMPRE (daí o `finally`), o BERCO-DE-TMP-01 leva embora o
    `/tmp` desta sessão. Depois de tudo, e não antes, porque a cópia congelada
    da ARVORE-CONGELADA-01 mora dentro do berço: varrer primeiro apagaria o
    lado esquerdo da comparação que decide se o produto mudou no meio da
    medição.
    """
    try:
        _sessionfinish_das_guardas(session)
    finally:
        _varrer_berco(session, getattr(session, "exitstatus", exitstatus))


def _sessionfinish_das_guardas(session: Any) -> None:
    """GUARDA-GI-REAL-01 + ARVORE-CONGELADA-01 + CANARIO-FS-01, nesta ordem."""
    if EXIGE_GTK_REAL and _MODULOS_PULADOS_SEM_GI:
        session.exitstatus = 1

    # ARVORE-CONGELADA-01, segunda metade: o produto mudou DEBAIXO da medição?
    # Então este run não mediu uma coisa só, e nenhum verde nem vermelho dele
    # vale. Reprovar é a única saída honesta: um verde falso passa despercebido
    # para sempre, e foi assim que uma mordida real foi declarada inexistente.
    deltas_produto = _deltas_do_congelado()
    if deltas_produto:
        mostrados = deltas_produto[:_CONGELADA_LIMITE_RELATO]
        restam = len(deltas_produto) - len(mostrados)
        _escrever_no_terminal(session, [
            "",
            "ARVORE-CONGELADA-01: o PRODUTO mudou durante esta sessão "
            f"({len(deltas_produto)} arquivo(s)):",
            *[f"  - {d}" for d in mostrados],
            *([f"  ... e mais {restam}"] if restam > 0 else []),
            "  A bancada mediu a foto do início; a árvore de hoje é outra. Este",
            "  run NÃO decide nada — nem o verde, nem o vermelho. Rode de novo",
            "  com a árvore parada (um mutador por vez, ou um git worktree por",
            "  agente) antes de gravar qualquer nota que dependa dele.",
        ])
        session.exitstatus = 1

    if not _canario_ligado() or not _CANARIO_ARMADO:
        return

    # As árvores de AVISO primeiro, porque elas NÃO reprovam e não podem ser
    # engolidas por um `return` do bloco que reprova.
    deltas_aviso = _deltas_do_canario(
        _CANARIO_FOTO_AVISO, _fotografar_tudo_de_aviso()
    )
    if deltas_aviso:
        mostrados = deltas_aviso[:_CANARIO_LIMITE_AVISO]
        restam = len(deltas_aviso) - len(mostrados)
        _escrever_no_terminal(session, [
            "",
            "CANARIO-FS-01 (aviso, não é portão): mudou durante a sessão, em "
            f"árvore que a suíte não devia provocar ({len(deltas_aviso)}):",
            *[f"  - {d}" for d in mostrados],
            *([f"  ... e mais {restam}"] if restam > 0 else []),
            "  Quase sempre isto NÃO é a suíte escrevendo: é o daemon VIVO dela",
            "  reagindo ao que a suíte faz em /dev/input (procure no journal por",
            "  `backend_hotplug_reconcile trigger=input_dir_change`). Ver a",
            "  SUITE-QUE-SUJA-O-JORNAL-01. Nada aqui é restaurado: escrita da",
            "  daemon dela é trabalho real, e desfazê-la seria o dano maior.",
        ])

    deltas = _deltas_do_canario(_CANARIO_FOTO_INICIAL, _fotografar_tudo())
    if not deltas:
        return
    linhas = [
        "",
        "CANARIO-FS-01: a suíte ESCREVEU nos diretórios reais da usuária "
        f"({len(deltas)} mudança(s)):",
        *[f"  - {d}" for d in deltas],
        "  Um teste hermético não deixa rastro em $HOME. Procure constante de",
        "  módulo com Path.home() avaliada no import (monkeypatch de HOME não a",
        "  alcança) — mova para função e injete o caminho.",
        f"  Se o daemon/GUI estava rodando ao lado, {_CANARIO_DESLIGADO_ENV}=1 "
        "desliga este canário.",
    ]
    _escrever_no_terminal(session, linhas)
    session.exitstatus = 1


# NOTA: a sonda antiga `_gtk_response_type_ausente()` foi fundida em
# `_sondar_gtk_do_ambiente()` acima — um subprocesso responde as DUAS
# perguntas (gi real? ResponseType presente?) em vez de dois.


# ---------------------------------------------------------------------------
# ARVORE-CONGELADA-01 — o produto MEDIDO não pode mudar no meio da medição
# ---------------------------------------------------------------------------
#
# O DEFEITO, MEDIDO em 06/08/2026 (diagnóstico com reprodução em três braços):
# uma bancada que roda `bash /caminho/absoluto/da/arvore/scripts/x.sh` mede o
# arquivo que estiver no disco NAQUELE INSTANTE. Quando outro processo edita
# esse arquivo durante a sessão — um agente irmão fazendo "arrancar a cura ->
# rodar -> devolver", um `git checkout` noutro terminal, um editor salvando —
# a bancada mede o produto de outra pessoa. O braço de controle da reprodução:
#
#   bancada em cópia A, ninguém mutando A ......... 0 falhas / 10
#   bancada em cópia A, mutador ciclando em A ..... 5 falhas / 10 (testes
#                                                   DIFERENTES a cada rodada)
#   bancada em cópia B, mutador ciclando em A ..... 0 falhas / 10
#
# O terceiro braço é a prova de que o canal é o ARQUIVO COMPARTILHADO, e não
# carga da máquina nem concorrência entre execuções (18 `pytest` simultâneos na
# árvore real: 0 falhas / 18).
#
# E a contaminação vai nos DOIS sentidos, o que é o pior da história: mutação
# alheia viva produz VERMELHO FALSO (mordida afirmada que não existe), e um
# `cp ORIG` alheio que desfaz a sua mutação antes do `pytest` rodar produz
# VERDE FALSO (mordida real declarada inexistente). É exatamente a classe que
# a regra "teste tem de MORDER" existe para impedir.
#
# A CURA que não depende de disciplina de processo: a bancada não lê a árvore
# de trabalho — lê uma CÓPIA tirada UMA VEZ, no início da sessão. O que roda
# continua sendo o que está na árvore no instante em que o `pytest` começou
# (então arrancar uma cura ANTES de rodar continua ficando vermelho, como tem
# de ser); o que deixa de existir é a janela em que o arquivo muda DEBAIXO da
# medição.
#
# Não substitui o CANARIO-FS-01 acima: aquele vigia o `$HOME` DELA contra
# escrita da suíte; este protege a MEDIÇÃO contra escrita de terceiros.

#: O que uma bancada de shell precisa enxergar. Lista explícita de propósito:
#: `packaging/cosmic-applet/target` tem 18 GB e copiar a árvore inteira seria
#: trocar um defeito por outro.
_CONGELAR: tuple[str, ...] = (
    "scripts",
    "assets/bluetooth",
    "flatpak",
    "packaging/arch",
    "packaging/debian",
    "packaging/fedora",
    "packaging/nix",
    ".github/workflows",
    "install.sh",
    "uninstall.sh",
)

#: Lixo de build que nunca é produto.
_CONGELAR_IGNORAR = ("__pycache__", "target", ".flatpak-builder", "build", "*.pyc")


def _e_lixo_de_build(relativo: Path) -> bool:
    """O caminho cai em `_CONGELAR_IGNORAR`? Então não é produto, nos DOIS lados.

    Existe porque a foto e a comparação precisam concordar sobre o que é
    produto. Medido em 12/08/2026: a cópia congelada nasce sem um único
    `.pyc` (o `copytree` já ignora), mas quem IMPORTA um script de dentro
    dela — `tests/unit/test_gravador_recusa_com_daemon_vivo.py` faz isso pelo
    `importlib`, e é o comportamento normal do CPython — deixa o bytecode
    nascer LÁ DENTRO, depois da foto. Na comparação final esse `.pyc` não
    tinha par na árvore viva e a guarda o relatava como
    `APAGADO scripts/__pycache__/record_hid_capture.cpython-312.pyc`,
    reprovando com código 1 uma sessão de cinco testes verdes — inclusive o
    job `lint-test` do CI, desde 11/08/2026.

    Isto explica o que JÁ funcionava: a guarda passou dias correta porque
    nenhuma bancada importava de dentro do congelado, só executava por
    `subprocess` (o `__main__` de um script não gera `__pycache__`).

    A cura NÃO é afrouxar a guarda: o filtro é exatamente a mesma lista que a
    foto usou. Um arquivo de produto de verdade continua sendo acusado.
    """
    return any(
        fnmatch.fnmatch(parte, padrao)
        for parte in relativo.parts
        for padrao in _CONGELAR_IGNORAR
    )

#: Preenchido na primeira chamada e nunca mais — a foto é da SESSÃO.
_ARVORE_CONGELADA: list[Path] = []


def arvore_congelada() -> Path:
    """Cópia só-leitura da árvore, tirada UMA VEZ por sessão de `pytest`.

    Use-a como raiz em toda bancada que EXECUTA um arquivo do repositório
    (``bash scripts/...``) em vez de apenas lê-lo: é o que impede que uma
    escrita de terceiro no meio da sessão vire falha (ou aprovação) inventada.
    Ver ARVORE-CONGELADA-01 acima.
    """
    if _ARVORE_CONGELADA:
        return _ARVORE_CONGELADA[0]

    import atexit
    import shutil
    import tempfile

    origem_raiz = Path(__file__).resolve().parents[1]
    destino = Path(tempfile.mkdtemp(prefix="hefesto-arvore-congelada-"))
    atexit.register(shutil.rmtree, destino, True)
    ignorar = shutil.ignore_patterns(*_CONGELAR_IGNORAR)
    for relativo in _CONGELAR:
        origem = origem_raiz / relativo
        alvo = destino / relativo
        if origem.is_dir():
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(origem, alvo, ignore=ignorar, symlinks=True)
        elif origem.is_file():
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origem, alvo)
    _ARVORE_CONGELADA.append(destino)
    return destino


#: Teto de linhas do relatório — uma sessão contaminada de verdade muda poucos
#: arquivos; se mudou centenas, a lista inteira não ajuda ninguém.
_CONGELADA_LIMITE_RELATO = 20


def _deltas_do_congelado() -> list[str]:
    """O produto MUDOU entre a foto e o fim da sessão? Diga quais arquivos.

    Congelar torna o veredito COERENTE (uma sessão inteira mede o mesmo
    produto) — não torna a bancada imune: uma mutação que já estivesse viva no
    instante da foto é medida a sessão inteira, e é indistinguível de um defeito
    de verdade, como TEM de ser (é assim que se prova mordida). O que faltava era
    a outra metade: DIZER quando isso aconteceu, em vez de acreditar no veredito.
    Sem isto, um `cp ORIG` de terceiro no meio da sessão desfaz a sua mutação e
    a suíte declara VERDE uma mordida real — o pior dos dois erros.

    O LIMITE DESTA SONDA, MEDIDO e declarado para ninguém a tomar por garantia:
    ela compara DOIS INSTANTES (a foto e o fim), não vigia o intervalo. Numa
    reprodução de 06/08/2026 com um mutador ciclando a 2 Hz na árvore durante
    dez execuções, a sonda acusou 3 das 10 — e as 7 restantes eram sessões em
    que a árvore estava no MESMO estado nos dois instantes. O que a sonda pega
    de graça é o caso que mais engana: a árvore mexida e devolvida (ou mexida e
    deixada mexida) enquanto a suíte roda. O ganho grande da mesma reprodução é
    outro, e esse é total: as falhas deixaram de ser SORTEADAS. Antes, testes
    diferentes caíam a cada rodada; depois, TODA rodada vermelha caiu no mesmo
    conjunto de quatro — exatamente a mordida pretendida da mutação viva.
    Vermelho reproduzível é diagnosticável; vermelho sorteado não é.
    """
    if not _ARVORE_CONGELADA:
        return []
    congelada = _ARVORE_CONGELADA[0]
    viva = Path(__file__).resolve().parents[1]
    deltas: list[str] = []
    for copia in sorted(congelada.rglob("*")):
        if not copia.is_file():
            continue
        relativo = copia.relative_to(congelada)
        # Bytecode que NASCEU dentro do congelado (um `importlib` de bancada)
        # não é produto e não tem par na árvore viva. Ver `_e_lixo_de_build`.
        if _e_lixo_de_build(relativo):
            continue
        atual = viva / relativo
        if not atual.is_file():
            deltas.append(f"APAGADO  {relativo}")
            continue
        try:
            if atual.read_bytes() != copia.read_bytes():
                deltas.append(f"MUDADO   {relativo}")
                continue
        except OSError:
            deltas.append(f"ILEGÍVEL {relativo}")
            continue
        if (atual.stat().st_mode & 0o777) != (copia.stat().st_mode & 0o777):
            deltas.append(f"MODO     {relativo}")
    return deltas


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _hefesto_fake_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ativa HEFESTO_DUALSENSE4UNIX_FAKE=1 e ISOLA os diretórios XDG em todo teste.

    FAKE=1 — garantia defensiva: subsystems que fazem probing de hardware real
    (TouchpadReader enumerando evdev, ex.) devem pular a inicialização quando o
    flag está presente — caso contrário testes em ambiente dev com DualSense
    conectado sofrem latência extra (>60ms) que empurra janelas de teste curtas
    para fora do budget. FakeController já é o padrão nas suítes; o env var apenas
    torna esse contrato explícito para outros módulos consumirem.

    BUG-TEST-CONFIG-LEAK-01 — isola XDG_CONFIG_HOME (e data/cache/state/runtime)
    num tmp por teste. `utils.xdg_paths.config_dir()` resolve via `platformdirs`,
    que respeita `XDG_CONFIG_HOME`; sem isolamento, qualquer teste que sobe o
    Daemon lia o `~/.config/hefesto-dualsense4unix` REAL do dev e herdava as flags
    de sessão (gamepad/mouse/paused), o session.json e os profiles. Numa máquina
    com a emulação de gamepad LIGADA de verdade, o daemon de teste nascia com o
    gamepad ativo e os testes de dispatch de mouse/teclado/hotkey
    (test_poll_loop_evdev_cache, test_keyboard_wire_up) falhavam — enquanto a CI
    (HOME limpo) passava. Isolar torna a suíte hermética e independente do estado
    real do dev. Testes que precisam de config própria continuam livres para
    monkeypatchar `config_dir`/`XDG_CONFIG_HOME` por cima.
    """
    if not os.environ.get("HEFESTO_DUALSENSE4UNIX_FAKE"):
        monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_FAKE", "1")
    # XDG_RUNTIME_DIR NÃO é isolado de propósito: os testes de single_instance
    # dependem da semântica real do runtime dir (pid/socket, permissões 0700) e
    # quebram sob um tmp. O socket IPC já é isolável por nome via
    # HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME quando um teste precisa.
    #
    # Os dirs ficam sob um subdir dedicado (`.xdg/`) para NÃO colidir com testes
    # que criam `tmp_path / "config"` etc. com `exist_ok=False` na própria fixture
    # (ex.: test_service_install.isolated_systemd_user) — pytest entrega o MESMO
    # tmp_path a todas as fixtures do teste. Testes que setam o próprio
    # XDG_CONFIG_HOME por cima continuam vencendo (este é só o default hermético).
    xdg_root = tmp_path / ".xdg"
    for var, sub in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_STATE_HOME", "state"),
    ):
        target = xdg_root / sub
        target.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(target))
    # FIX-PACKAGING-SEED-PARITY-01 — desliga a semeadura automática de presets
    # (profiles.loader._maybe_seed_presets). Sem isto, o PRIMEIRO teste do
    # processo a carregar perfis receberia os JSONs de assets/profiles_default/
    # do repo no seu tmp (o flag once-per-process faria só um teste, dependente
    # da ordem, quebrar asserções de listas exatas). Os testes da semeadura
    # chamam seed_default_presets() com paths injetados ou re-habilitam via
    # monkeypatch (delenv + _seed_attempted=False).
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED", "1")
    # BROKER-01: aponta o cliente do broker hide-hidraw para um socket
    # INEXISTENTE em TODO teste. Na máquina da mantenedora o broker REAL está
    # de pé em /run/hefesto-hidraw-broker/broker.sock — um teste que
    # resolvesse o default esconderia/abriria hidraw DE VERDADE no meio da
    # suíte. Testes do próprio cliente passam o caminho explicitamente.
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(xdg_root / "no-broker.sock"))
    # DIÁRIO-QUE-NAO-MENTE-01 (15/08/2026) — mesma classe do BROKER-01 acima, e
    # medida ao vivo: vários testes rodam os scripts `bt_*.sh` DE VERDADE, e
    # eles registram no journal. Os DADOS já eram isolados (raízes em tmp); o
    # LOG não era. Em 15/08 a suíte escreveu 3.221 linhas no journal DELA (2.199
    # do autorestore, 535 do snapshot, 422 do rebind, 65 da vigia) — 36 delas
    # dizendo "bluetooth.service morreu (SERVICE_RESULT=oom-kill)" sobre
    # um bluetoothd que nunca morreu (systemctl: Result=success, ativo desde as
    # 14:14). Oito dessas linhas caíram entre 18h29 e 21h38 e custaram vinte
    # minutos de caçada a um defeito inexistente.
    #
    # O default aqui DESVIA, não emudece: as linhas continuam sendo escritas,
    # num arquivo por teste que o próprio teste pode ler. Um teste que precise
    # do caminho de produção passa `HEFESTO_BT_LOG_DEST=""` explicitamente — e
    # é isso que faz esta variável ser um portão e não um interruptor: quem
    # quiser o journal tem de pedir por escrito.
    monkeypatch.setenv("HEFESTO_BT_LOG_DEST", str(xdg_root / "bt-log.txt"))
    # CARONA-DO-WRAPPER-01 (16/08/2026) — mesma classe do BROKER-01 acima, e o
    # risco é maior: salvar ou aplicar um perfil passou a repor, de carona, a
    # chamada do `hefesto-launch` nas Opções de Inicialização da Steam
    # (`app/actions/carona_do_wrapper.py`). Isso varre o `localconfig.vdf` e,
    # com a Steam fechada, ESCREVE nele. Dezenas de testes de GUI chamam
    # "Salvar Perfil"; sem esta linha, uma suíte rodando na máquina dela
    # reescreveria a biblioteca inteira dela em segundo plano — e o `HOME` NÃO
    # é isolado nesta suíte (o `discover_vdfs` resolve `Path.home()`).
    #
    # Desligado em TODO teste, e quem quer exercitar a carona religa por
    # escrito, com fixtures em `tmp_path` (é o que o
    # `test_carona_do_wrapper_01_*.py` faz). Não é flag de produto: em produção
    # a variável não existe e a carona está sempre ligada.
    monkeypatch.setenv("HEFESTO_CARONA_WRAPPER", "0")


# ---------------------------------------------------------------------------
# PARIDADE-BYTE-01 — o transporte vira DIMENSÃO do caso, não rótulo num dict
# ---------------------------------------------------------------------------
#
# O PORQUÊ, MEDIDO em 10/08/2026 contra os 8589 testes coletados (o diagnóstico
# inteiro está na seção 2 do índice
# `docs/process/sprints/2026-08-10-INDICE-o-mapa-que-vira-portao.md`):
#
#   testes que MENCIONAM transporte ................... 718 (9,7%)
#   testes que tocam o envelope no nível de BYTE ......  93 (1,1%)
#   `parametrize` cruzando os DOIS transportes ........   0, de 233
#   fixtures parametrizadas por transporte ............   0
#   capturas HID gravadas na suíte ....................   1, e é USB
#
# E a prova por mutação, que é a que não deixa dúvida: trocar **R por B** dentro
# de `_build_common` (vermelho vira azul na lightbar) deixava a suíte INTEIRA
# verde — 8584 passaram; e matar os gatilhos adaptativos **só no BT**, com
# envelope e CRC perfeitos, reprovava **1 teste em 8589** — e era o genérico "o
# payload sai verbatim", que não sabe o que é gatilho.
#
# O diagnóstico em uma frase: cada feature era provada UMA vez, no transporte
# que estava na mesa de quem escreveu o teste — quase sempre o cabo.
#
# A CURA é esta fixture: `transporte` é PARAMETRIZADA (`usb` e `bt`), então todo
# caso que a pede roda DUAS vezes, com ids `[usb]` e `[bt]`, e reprova quando um
# dos lados quebra sozinho.
#
# O QUE ELA NÃO FAZ, DE PROPÓSITO: reimplementar o envelope. Uma fixture que
# monta o 0x31 por conta própria mede a si mesma — é a armadilha nº 1 desta casa
# (o instrumento brigando com o produto). Todo valor aqui ou é uma constante
# importada de `core/ds_output_report.py`, ou é MEDIDO chamando o builder de
# produção: o deslocamento do common não está escrito em lugar nenhum daqui,
# `_medir_deslocamento_do_common` procura um payload marcado DENTRO do report
# que a produção montou.

#: Os dois transportes que o DualSense fala, nos nomes que a casa usa (são os
#: mesmos do `Transport` do backend e das colunas `cabo_*`/`radio_*` do mapa).
TRANSPORTES: tuple[str, ...] = ("usb", "bt")


def _montar_usb(common: bytes | bytearray, *, seq: int = 0) -> bytearray:
    """Adaptador de assinatura: o 0x02 não tem sequência, e `seq` é inócuo.

    Existe para que o caso de teste chame `transporte.montar(common, seq=…)`
    sem saber em qual transporte está — que é justamente o ponto de o
    transporte ser dimensão do caso. Não monta nada: delega ao builder de
    produção.
    """
    from hefesto_dualsense4unix.core import ds_output_report as rep

    return rep.build_usb_report(common)


def _medir_deslocamento_do_common(montar: Callable[..., bytearray]) -> int:
    """Onde o common de 47 bytes CAI dentro do report que a produção monta.

    Medido, não declarado: monta um common marcado (0,1,2,…,46 — uma sequência
    que não se repete no envelope) e procura essa subsequência no buffer. Se um
    dia o envelope mudar de forma, este número muda junto com o produto, em vez
    de virar uma segunda verdade que ninguém atualiza.
    """
    from hefesto_dualsense4unix.core import ds_output_report as rep

    marcado = bytes(range(rep.COMMON_LEN))
    posicao = bytes(montar(marcado)).find(marcado)
    if posicao < 0:
        raise RuntimeError(
            "o builder de produção não embutiu o common marcado no report — "
            "o envelope mudou de forma e a fixture de transporte não sabe medi-lo"
        )
    return posicao


@dataclass(frozen=True)
class EnvelopeDeTransporte:
    """Tudo que separa o cabo do rádio, do report id ao CRC.

    Os campos respondem, para UM transporte, as perguntas que o diagnóstico de
    10/08 mostrou que nenhum teste fazia duas vezes:

    - `report_id` — 0x02 no cabo, 0x31 no rádio;
    - `deslocamento_do_common` — 1 no cabo, 3 no rádio (MEDIDO no builder);
    - `tamanho_do_report` — 64 e 78;
    - `tag` — o 0x10 obrigatório do BT, ausente no USB;
    - `semente_do_crc` — 0xA2 no BT, `None` no USB (o cabo não tem CRC);
    - `tem_nibble_de_sequencia` — o nibble alto de `[1]`, só no BT.
    """

    nome: str
    nome_do_contype: str
    report_id: int
    tamanho_do_report: int
    deslocamento_do_common: int
    tag: int | None
    semente_do_crc: int | None
    tem_nibble_de_sequencia: bool
    montar: Callable[..., bytearray]

    @property
    def tipo_de_conexao(self) -> Any:
        """O membro de `ConnectionType` da pydualsense deste transporte."""
        from pydualsense.enums import ConnectionType

        return getattr(ConnectionType, self.nome_do_contype)

    def extrair_common(self, report: bytes | bytearray | list[int]) -> bytes:
        """Os 47 bytes de payload de dentro do envelope deste transporte."""
        from hefesto_dualsense4unix.core import ds_output_report as rep

        bruto = bytes(report)
        inicio = self.deslocamento_do_common
        return bruto[inicio : inicio + rep.COMMON_LEN]

    def sequencia_de(self, report: bytes | bytearray | list[int]) -> int | None:
        """O nibble de sequência do report, ou `None` onde ele não existe."""
        if not self.tem_nibble_de_sequencia:
            return None
        return (bytes(report)[1] >> 4) & 0x0F

    def crc_do_report(self, report: bytes | bytearray | list[int]) -> int | None:
        """O CRC-32 que ESTÁ gravado no report, ou `None` sem CRC."""
        if self.semente_do_crc is None:
            return None
        return int.from_bytes(bytes(report)[-4:], "little")

    def crc_esperado(self, report: bytes | bytearray | list[int]) -> int | None:
        """O CRC-32 que a receita de produção calcula, ou `None` sem CRC."""
        from hefesto_dualsense4unix.core import ds_output_report as rep

        if self.semente_do_crc is None:
            return None
        return rep.bt_crc32(bytes(report)[:-4], seed=self.semente_do_crc)

    def problemas_do_envelope(self, report: bytes | bytearray | list[int]) -> list[str]:
        """Lista legível do que está errado no envelope (vazia = está inteiro).

        É lista e não `assert` para o caso de teste poder dizer QUAL transporte
        quebrou na mensagem — o ponto inteiro desta camada é que "quebrou" nunca
        mais seja uma resposta sem lado.
        """
        from hefesto_dualsense4unix.core import ds_output_report as rep

        bruto = bytes(report)
        if len(bruto) != self.tamanho_do_report:
            return [
                f"{self.nome}: tamanho {len(bruto)}, esperado {self.tamanho_do_report}"
            ]
        problemas: list[str] = []
        if bruto[0] != self.report_id:
            problemas.append(
                f"{self.nome}: report id {bruto[0]:#04x}, esperado {self.report_id:#04x}"
            )
        if self.tag is not None and bruto[2] != self.tag:
            problemas.append(
                f"{self.nome}: tag {bruto[2]:#04x}, esperado {self.tag:#04x} "
                "(o firmware descarta o 0x31 sem o tag mágico)"
            )
        fim_do_common = self.deslocamento_do_common + rep.COMMON_LEN
        fim_do_corpo = len(bruto) - (0 if self.semente_do_crc is None else 4)
        if any(bruto[fim_do_common:fim_do_corpo]):
            problemas.append(f"{self.nome}: há lixo no reservado depois do common")
        if self.semente_do_crc is not None:
            gravado = self.crc_do_report(bruto)
            esperado = self.crc_esperado(bruto)
            if gravado != esperado:
                problemas.append(
                    f"{self.nome}: CRC {gravado:#010x}, esperado {esperado:#010x}"
                )
        return problemas


#: Medido UMA vez por sessão, na primeira fixture que pedir (o import do módulo
#: de produção fica fora do topo do conftest de propósito: ele é avaliado na
#: coleta, e nada aqui pode depender de o pacote estar importável tão cedo).
_ENVELOPES: dict[str, EnvelopeDeTransporte] = {}


def _medir_os_transportes() -> dict[str, EnvelopeDeTransporte]:
    from hefesto_dualsense4unix.core import ds_output_report as rep

    return {
        "usb": EnvelopeDeTransporte(
            nome="usb",
            nome_do_contype="USB",
            report_id=rep.USB_REPORT_ID,
            tamanho_do_report=rep.USB_REPORT_LEN,
            deslocamento_do_common=_medir_deslocamento_do_common(_montar_usb),
            tag=None,
            semente_do_crc=None,
            tem_nibble_de_sequencia=False,
            montar=_montar_usb,
        ),
        "bt": EnvelopeDeTransporte(
            nome="bt",
            nome_do_contype="BT",
            report_id=rep.BT_REPORT_ID,
            tamanho_do_report=rep.BT_REPORT_LEN,
            deslocamento_do_common=_medir_deslocamento_do_common(rep.build_bt_report),
            tag=rep.BT_TAG,
            semente_do_crc=rep.BT_CRC_SEED,
            tem_nibble_de_sequencia=True,
            montar=rep.build_bt_report,
        ),
    }


def envelope_de(nome: str) -> EnvelopeDeTransporte:
    """O envelope de UM transporte pelo nome (`"usb"` / `"bt"`)."""
    if not _ENVELOPES:
        _ENVELOPES.update(_medir_os_transportes())
    return _ENVELOPES[nome]


@pytest.fixture(params=["usb", "bt"])
def transporte(request: Any) -> EnvelopeDeTransporte:
    """O transporte como DIMENSÃO do caso: todo teste que a pede roda 2x.

    Os ids saem `[usb]` e `[bt]`, então o relatório do pytest diz qual LADO
    quebrou — que é a informação que faltava em 10/08, quando matar os gatilhos
    só no BT reprovava um único teste genérico.

    OS DOIS NOMES ESTÃO ESCRITOS À MÃO NO DECORADOR, e não como `TRANSPORTES`,
    de propósito: quem faz o CENSO desta camada lê o código com `ast`, e uma
    indireção (`params=TRANSPORTES`) some do censo — a fixture existiria e o
    portão continuaria contando zero. `test_paridade_transporte_envelope.py`
    trava as duas listas juntas para que a duplicação não possa divergir.
    """
    return envelope_de(str(request.param))


@pytest.fixture()
def transportes() -> tuple[EnvelopeDeTransporte, ...]:
    """Os DOIS envelopes de uma vez, para o caso que os COMPARA entre si.

    Complementa a `transporte` (que roda um por vez): há afirmação do produto
    que só existe no cruzamento — "o common de 47 bytes é IDÊNTICO nos dois
    transportes, muda só o envelope" não cabe num caso que enxerga um lado.
    """
    return tuple(envelope_de(nome) for nome in TRANSPORTES)


@pytest.fixture()
def fabrica_de_bancada(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Any]:
    """Fábrica de `_PinnedPyDualSense` SEM device, num transporte escolhido.

    O handle nasce pelo `__init__` de produção (que não toca em hardware) e
    ganha à mão só o que o `init()` criaria DEPOIS de achar o device — as
    quatro peças de estado (`light`, `audio`, `triggerL`, `triggerR`) e o
    `conType`. Nada de estado privado escrito à mão: `_rumble_active`,
    `_volumes_audio`, `_preamp_audio` e companhia vêm do construtor de verdade,
    e é por isso que este handle não vira uma segunda implementação do produto.

    A ARMADILHA Nº 1 DESTA CASA FICA FECHADA AQUI: `prepareReport` tem um
    `except Exception` que cai no report do UPSTREAM (cujo 0x31 é malformado).
    Um atributo faltando na bancada faria o teste medir a pydualsense e chamar
    isso de produto — instrumento brigando com o produto, medição inventada.
    Com este monkeypatch, o fallback EXPLODE em vez de mentir.

    É fábrica, e não um handle pronto, porque há afirmação que só existe no
    CRUZAMENTO: comparar o report do cabo com o do rádio exige os dois handles
    vivos no mesmo caso.
    """
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger, pydualsense

    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    def _fallback_proibido(self: Any) -> list[int]:
        raise AssertionError(
            "prepareReport caiu no fallback do upstream: a bancada está "
            "incompleta e o teste mediria a pydualsense, não o hefesto"
        )

    monkeypatch.setattr(pydualsense, "prepareReport", _fallback_proibido)

    def _fabricar(envelope: EnvelopeDeTransporte) -> Any:
        handle = _PinnedPyDualSense(b"/dev/hidraw-de-bancada", is_edge=False)
        handle.light = DSLight()
        handle.audio = DSAudio()
        handle.triggerL = DSTrigger()
        handle.triggerR = DSTrigger()
        handle.conType = envelope.tipo_de_conexao
        handle.input_report_length = envelope.tamanho_do_report
        handle.output_report_length = envelope.tamanho_do_report
        return handle

    return _fabricar


@pytest.fixture()
def ds5_de_bancada(
    transporte: EnvelopeDeTransporte, fabrica_de_bancada: Callable[..., Any]
) -> Any:
    """O handle de bancada do transporte DESTE caso (ver `fabrica_de_bancada`)."""
    return fabrica_de_bancada(transporte)


@pytest.fixture(autouse=True, scope="session")
def _nenhum_uinput_de_verdade() -> Iterator[None]:
    """A suíte NÃO cria aparelho de entrada no kernel de quem a roda.

    **O defeito, medido em 20/08/2026, e ele saiu da máquina dela.** Ela relatou
    janelas saindo de tela cheia sozinhas e suspeitou de tecla presa. O kernel
    contava outra história: **1289 nós `Hefesto - Dualsense4Unix Virtual
    Keyboard` criados naquele dia**, 51 nos últimos trinta minutos, cada um
    vivendo cerca de 0,4 ms. Eram meus: cada `pytest -q` cria centenas deles, e a
    suíte rodou quinze vezes naquela sessão.

    **Por que isso derrubava a tela cheia dela sem ninguém apertar nada:** para o
    compositor Wayland cada add/remove de teclado é um re-assentamento de seat, e
    superfície em tela cheia costuma largar o fullscreen numa troca de foco. Não
    é preciso Esc nenhum — e foi atrás do Esc que eu fui primeiro, ancorada em
    duas linhas de log que depois se provaram falsas.

    **A raiz não é a suíte ser desleixada — é a máquina dela ser a mesma.** Aqui
    a máquina de desenvolvimento é a máquina em que ela joga, trabalha e assiste.
    Uma suíte que mexe em `/dev/input` não está num ambiente isolado: está
    escrevendo entrada de verdade, por cima da sessão de uma pessoa que está
    usando o computador.

    São dois pontos de criação, e só dois — `integrations/uinput_keyboard.py` e
    `integrations/uinput_mouse.py`, ambos fazendo `import uinput` DENTRO da
    função e chamando `uinput.Device(...)`. Por isso a troca é em
    `sys.modules["uinput"].Device`: pega os dois sem que nenhum dos dois precise
    saber que está sendo dublado.

    Custo em produção: ZERO. Isto vive só na suíte.
    """
    try:
        import uinput  # type: ignore[import-not-found]
    except ImportError:
        # Sem a biblioteca não há tempestade a impedir — e é o caso do CI.
        yield
        return

    class _AparelhoDeMentira:
        """Aceita o que o `uinput.Device` aceita, e não fala com o kernel."""

        def __init__(self, capabilities: object, name: str = "", **_kw: object) -> None:
            self.capabilities = capabilities
            self.name = name
            self.emitidos: list[tuple[object, ...]] = []

        def emit(self, *args: object, **_kw: object) -> None:
            self.emitidos.append(args)

        def syn(self) -> None:
            pass

        def destroy(self) -> None:
            pass

        def __enter__(self) -> "_AparelhoDeMentira":
            return self

        def __exit__(self, *_exc: object) -> None:
            pass

    verdadeiro = uinput.Device
    uinput.Device = _AparelhoDeMentira  # type: ignore[misc,assignment]
    try:
        yield
    finally:
        uinput.Device = verdadeiro  # type: ignore[misc]


@pytest.fixture(autouse=True, scope="session")
def _nenhum_sysfs_vivo_na_varredura_de_vpad(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """A varredura de `/sys/class/input` do `state_full` aponta para o VAZIO.

    Irmã da `_nenhum_uinput_de_verdade` logo acima, e pela mesma razão: a
    máquina de desenvolvimento é a máquina dela, e ali há vpads de VERDADE em
    `/sys/class/input`. A `integrations/no_do_vpad.resolver_no_do_vpad` roda
    dentro do `_handle_daemon_state_full`, que dezenas de testes chamam — sem
    esta fixture, cada um deles leria o sysfs vivo e o payload sob teste
    passaria a depender de quantos controles estavam ligados no momento.

    Não é só hermetismo: um teste que casasse com o `event22` de verdade dela
    estaria afirmando sobre o aparelho dela, e afirmação sobre aparelho nesta
    casa se mede na bancada, nunca na suíte.

    Vazio, e não um dublê: quem PRECISA de uma árvore forjada a monta e
    aponta as constantes para ela com `monkeypatch` (escopo de função, que
    desfaz por cima desta). O default da suíte é "não achei nó nenhum", que é
    a resposta honesta de uma máquina sem vpad.
    """
    vazio = tmp_path_factory.mktemp("sysfs-sem-vpad")
    try:
        from hefesto_dualsense4unix.integrations import no_do_vpad
    except ModuleNotFoundError as erro:  # pragma: no cover - só no job leve do CI
        # O job "A casa sabe e o produto não faz" do `ci.yml` instala SÓ o
        # pytest, de propósito: é um portão de doze segundos que LÊ a árvore e
        # nunca importa o produto. Esta fixture é `autouse=True` de escopo de
        # SESSÃO, então ao nascer em 20/08 (e0a5837) passou a importar o
        # produto em toda sessão de pytest — e vermelhou os 28 testes daquele
        # portão, nenhum dos quais toca em vpad. O CI de main ficou vermelho
        # nos dois repositórios desde então.
        #
        # Sem o pacote instalado NÃO HÁ o que blindar: a varredura de sysfs
        # que esta fixture aponta para o vazio mora dentro do produto, e quem
        # a chamasse já teria estourado no próprio import. O `except` é
        # estreito de propósito — se faltar qualquer OUTRO módulo, propaga,
        # porque aí a ausência é defeito e não desenho.
        if (erro.name or "").split(".")[0] != "hefesto_dualsense4unix":
            raise
        yield
        return

    antes = (
        no_do_vpad.RAIZ_CLASS_INPUT,
        no_do_vpad.RAIZ_DEV_INPUT,
        no_do_vpad.RAIZ_DEV,
    )
    no_do_vpad.RAIZ_CLASS_INPUT = str(vazio / "class-input")
    no_do_vpad.RAIZ_DEV_INPUT = str(vazio / "dev-input")
    no_do_vpad.RAIZ_DEV = str(vazio / "dev")
    try:
        yield
    finally:
        (
            no_do_vpad.RAIZ_CLASS_INPUT,
            no_do_vpad.RAIZ_DEV_INPUT,
            no_do_vpad.RAIZ_DEV,
        ) = antes
