"""As fontes da interface moram no produto, e a janela não espera a internet.

AS-FONTES-DA-INTERFACE-MORAM-NO-PRODUTO-01 (23/10/2026). O defeito, medido no fecho da leva
fim-da-fila: as dez páginas pediam a fonte ao Google num `<link>`, e uma folha de estilo externa
segura o `document.readyState` antes do `complete` enquanto a rede não responde. A régua de tela e o
produto, no mesmo WebKitGTK, esperavam a rede. Com `https_proxy=http://10.255.255.1:9` os mesmos
testes reprovavam sempre (`CargaFalhou` aos 20 s).

A CURA, NA ORIGEM: Space Grotesk e JetBrains Mono (OFL) vêm em `interface/assets/fontes/`, e um
`@font-face` do `topo.html` troca o `<link>`. As réguas:

1. nenhuma página (`topo.html`, `mockup/NN-*.html`, `paginas/NN-*.html`) pede recurso fora da
   máquina: `<link>`, `<script src>`, imagem, `url(` e `@import`; o namespace do SVG e o `<a>`
   não contam;
2. todo `@font-face` aponta para um arquivo que existe, está dentro do pacote e é uma fonte de
   verdade;
3. a licença e a origem (versão e SHA-256) estão ao lado, o pacote leva a pasta, e o `.deb` não
   leva o link `assets/fontes` do mockup quebrado;
4. no WebKit, com a rede que não responde, a 02 e a 10 chegam ao `complete` em menos de 3 s e o
   `document.fonts` diz que as duas famílias carregaram;
5. a mordida da 4 mora no próprio arquivo: com o `<link>` do Google de volta, a mesma página
   NÃO abre.

AS-PAGINAS-DE-FORA-DAS-ABAS-LEVAM-A-LETRA-DA-CASA-01 (27/10/2026): o Calibrar giroscópio, o Mapa
das portas e o Mapa do rádio entram nas réguas 1 e 2, no desenho e no publicado, e a variável do
corpo de cada uma começa pela Space Grotesk, e a do dado pela JetBrains Mono. O publicado que o
`mockup/DIVERGENCIAS.md` declara em trabalho espera o `--publicar` (xfail estrito: o publicar tira
a declaração e cura a página no mesmo gesto). No WebKit, as três do desenho carregam as duas
famílias; sem o `@font-face`, o Calibrar não carrega a Space Grotesk.
"""
from __future__ import annotations

import hashlib
import html.parser
import json
import os
import pathlib
import re
import subprocess
import sys

import importlib.util

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
FONTES = INTERFACE / "assets" / "fontes"
MOCKUP = RAIZ / "mockup"
PUBLICADO = INTERFACE / "paginas"  # (noqa-acento)
TOPO = INTERFACE / "topo.html"

REDE_MUDA = "http://10.255.255.1:9"

NUMEROS = tuple(f"{n:02d}" for n in range(1, 11))
FAMILIAS = {"Space Grotesk", "JetBrains Mono"}


def _as_dez(pasta: pathlib.Path) -> list[pathlib.Path]:
    return [p for n in NUMEROS for p in sorted(pasta.glob(f"{n}-*.html"))]


DE_FORA = ("calibrar-sensores.html", "mapa-das-portas.html", "mapa-do-radio.html")
VARIAVEIS_DE_FORA = {
    "calibrar-sensores.html": ("--f", "--m"),
    "mapa-das-portas.html": ("--font-corpo", "--font-dado"),
    "mapa-do-radio.html": ("--font-corpo", "--font-dado"),
}
JA_DIZIA_A_CASA = frozenset({"mapa-do-radio.html"})


def _declaradas() -> set[str]:
    """As páginas em trabalho, perguntado ao portão `desenho-aprovado`, o dono."""
    alvo = RAIZ / "scripts" / "check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_das_fontes", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_das_fontes"] = mod
    spec.loader.exec_module(mod)
    declaradas: set[str] = mod.declaradas()
    return declaradas


_EM_TRABALHO = _declaradas()


def _de_fora(pasta: pathlib.Path) -> list[pathlib.Path]:
    return [pasta / nome for nome in DE_FORA]


def _com_a_espera(arq: pathlib.Path) -> object:
    """O publicado de fora declarado em trabalho espera o `--publicar` do fecho."""
    if arq.parent == PUBLICADO and arq.name in DE_FORA and arq.name in _EM_TRABALHO:
        return pytest.param(arq, marks=pytest.mark.xfail(
            strict=True, reason=f"{arq.name} declarada no DIVERGENCIAS até o --publicar"))
    return arq


PAGINAS = [TOPO, *_as_dez(MOCKUP), *_as_dez(PUBLICADO), *_de_fora(MOCKUP), *_de_fora(PUBLICADO)]
COM_A_ESPERA = [_com_a_espera(p) for p in PAGINAS]


def _id(caminho: pathlib.Path) -> str:
    return str(caminho.relative_to(RAIZ))


_URL_NO_CSS = re.compile(r"""url\(\s*['"]?\s*((?:https?:)?//[^'")\s]+)""", re.I)
_IMPORT_NO_CSS = re.compile(r"""@import\s+(?:url\(\s*)?['"]?\s*((?:https?:)?//[^'")\s;]+)""", re.I)
_EXTERNA = re.compile(r"^\s*(?:https?:)?//", re.I)
_COM_SRC = frozenset(
    {"script", "img", "source", "iframe", "embed", "video", "audio", "track", "input"}
)


class _Recursos(html.parser.HTMLParser):
    """Tudo que a página PEDE a outra máquina. O que ela só aponta (`<a>`) fica de fora."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.externos: list[str] = []
        self._em_estilo = False

    def _css(self, texto: str) -> None:
        self.externos += _URL_NO_CSS.findall(texto) + _IMPORT_NO_CSS.findall(texto)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "link" and _EXTERNA.match(a.get("href", "")):
            self.externos.append(a["href"])
        if tag in _COM_SRC and _EXTERNA.match(a.get("src", "")):
            self.externos.append(a["src"])
        if tag in {"image", "use"}:
            for chave in ("href", "xlink:href"):
                if _EXTERNA.match(a.get(chave, "")):
                    self.externos.append(a[chave])
        if "style" in a:
            self._css(a["style"])
        if tag == "style":
            self._em_estilo = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._em_estilo = False

    def handle_data(self, data: str) -> None:
        if self._em_estilo:
            self._css(data)


def recursos_de_fora(texto: str) -> list[str]:
    leitor = _Recursos()
    leitor.feed(texto)
    return leitor.externos


@pytest.mark.parametrize("arq", PAGINAS, ids=_id)
def test_nenhuma_pagina_pede_recurso_fora_da_maquina(arq: pathlib.Path) -> None:
    assert recursos_de_fora(arq.read_text(encoding="utf-8")) == []


def test_o_piso_sao_as_vinte_e_seis_paginas_e_o_topo() -> None:
    """Lista vazia aprovaria tudo: o piso é o que torna o verde uma medida."""
    assert len(_as_dez(MOCKUP)) == 10
    assert len(_as_dez(PUBLICADO)) == 10
    assert all(p.is_file() for p in [*_de_fora(MOCKUP), *_de_fora(PUBLICADO)])
    assert len(PAGINAS) == 27


@pytest.mark.parametrize(
    "texto",
    [
        '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk" rel="stylesheet">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<script src="https://cdn.exemplo.dev/x.js"></script>',
        "<style>@import url(https://exemplo.dev/a.css);</style>",
        '<style>@import "//exemplo.dev/a.css";</style>',
        "<style>a{background:url('https://exemplo.dev/a.png')}</style>",
        '<div style="background:url(//exemplo.dev/a.png)"></div>',
        '<img src="http://exemplo.dev/a.png">',
        '<svg><image xlink:href="https://exemplo.dev/a.png"/></svg>',
    ],
)
def test_a_regua_pega_cada_forma_de_recurso_de_fora(texto: str) -> None:
    """A régua morde: cada forma que a sprint manda proibir é achada."""
    assert recursos_de_fora(texto)


@pytest.mark.parametrize(
    "texto",
    [
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"></svg>',
        '<a href="https://github.com/exemplo/projeto">projeto</a>',
        '<link rel="stylesheet" href="base.css">',
        "<style>a{background:url('data:image/svg+xml;base64,AAAA')}</style>",
        "<style>@font-face{src:url('../assets/fontes/x.ttf')}</style>",
        '<svg><use href="#glifo"/></svg>',
    ],
)
def test_a_regua_deixa_passar_o_que_nao_e_recurso(texto: str) -> None:
    assert recursos_de_fora(texto) == []


_COMENTARIO_CSS = re.compile(r"/\*.*?\*/", re.S)
_FONT_FACE = re.compile(r"@font-face\s*\{([^}]*)\}")
_FAMILIA = re.compile(r"font-family\s*:\s*['\"]?([^;'\"]+)['\"]?\s*;")
_URL = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""")


def _casa_de(pagina: pathlib.Path) -> pathlib.Path:
    """De onde o endereço relativo se resolve: o `topo.html` é o molde e vira `paginas/`."""
    return PUBLICADO if pagina == TOPO else pagina.parent


def faces_de(texto: str) -> list[tuple[str, list[str]]]:
    """Cada `@font-face` da página: a família e os endereços do `src`."""
    sem_comentario = _COMENTARIO_CSS.sub("", texto)
    faces = []
    for bloco in _FONT_FACE.findall(sem_comentario):
        familia = _FAMILIA.search(bloco + ";")
        assert familia, f"@font-face sem família: {bloco[:80]}"
        faces.append((familia.group(1).strip(), [u for _aspas, u in _URL.findall(bloco)]))
    return faces


@pytest.mark.parametrize("arq", COM_A_ESPERA, ids=_id)
def test_todo_font_face_aponta_para_um_arquivo_do_pacote(arq: pathlib.Path) -> None:
    faces = faces_de(arq.read_text(encoding="utf-8"))
    assert {f for f, _ in faces} == FAMILIAS, f"as famílias declaradas em {_id(arq)}: {faces}"
    for familia, enderecos in faces:
        assert enderecos, f"{familia}: @font-face sem url() em {_id(arq)}"
        for endereco in enderecos:
            assert not _EXTERNA.match(endereco) and not endereco.startswith("data:"), endereco
            alvo = (_casa_de(arq) / endereco).resolve()
            assert alvo.is_file(), f"{familia}: {endereco} não existe a partir de {_id(arq)}"
            assert alvo.is_relative_to(FONTES.resolve()), (
                f"{alvo} fica fora do pacote ({FONTES}): o wheel não o leva"
            )
            magia = alvo.read_bytes()[:4]
            assert magia in {b"\x00\x01\x00\x00", b"true"}, f"{alvo.name} não é TrueType"


_SELETOR_NA_FRENTE = re.compile(r"[^\s{};>]\s*@font-face")


@pytest.mark.parametrize("arq", PAGINAS, ids=_id)
def test_nenhum_font_face_ganha_seletor_na_frente(arq: pathlib.Path) -> None:
    """A 08 põe `.radio` na frente de cada regra do primeiro `<style>` do Mapa do rádio: um
    `@font-face` ali vira `.radio @font-face`, que o navegador descarta."""
    texto = _COMENTARIO_CSS.sub("", arq.read_text(encoding="utf-8"))
    assert _SELETOR_NA_FRENTE.findall(texto) == [], _id(arq)


PESOS_DE_ANTES = {"Space Grotesk": "400 700", "JetBrains Mono": "400 500"}


@pytest.mark.parametrize("arq", COM_A_ESPERA, ids=_id)
def test_os_pesos_declarados_sao_os_que_o_link_do_google_pedia(arq: pathlib.Path) -> None:
    """Prova da D-2310-AS-FONTES-DA-INTERFACE-MORAM-NO-PRODUTO."""
    texto = _COMENTARIO_CSS.sub("", arq.read_text(encoding="utf-8"))
    achados = {}
    for bloco in _FONT_FACE.findall(texto):
        familia = _FAMILIA.search(bloco + ";")
        peso = re.search(r"font-weight\s*:\s*([0-9 ]+?)\s*;", bloco + ";")
        assert familia and peso, bloco[:80]
        achados[familia.group(1).strip()] = peso.group(1)
    assert achados == PESOS_DE_ANTES, f"{_id(arq)}: {achados}"


def _comeca_por(texto: str, variavel: str) -> str:
    achada = re.search(rf"{re.escape(variavel)}\s*:\s*([^;,]+)", _COMENTARIO_CSS.sub("", texto))
    assert achada, f"{variavel} não está declarada"
    return achada.group(1).strip().strip("'\"")


@pytest.mark.parametrize(
    "arq",
    [p if p.name in JA_DIZIA_A_CASA else _com_a_espera(p)
     for p in [*_de_fora(MOCKUP), *_de_fora(PUBLICADO)]],
    ids=_id)
def test_a_pagina_de_fora_comeca_pela_letra_da_casa(arq: pathlib.Path) -> None:
    """Prova da D-2710-AS-PAGINAS-DE-FORA-LEVAM-A-LETRA-DA-CASA: o corpo e o dado da casa."""
    texto = arq.read_text(encoding="utf-8")
    corpo, dado = VARIAVEIS_DE_FORA[arq.name]
    assert _comeca_por(texto, corpo) == "Space Grotesk", f"{_id(arq)}: {corpo}"
    assert _comeca_por(texto, dado) == "JetBrains Mono", f"{_id(arq)}: {dado}"


def test_o_mockup_e_o_publicado_chegam_ao_mesmo_arquivo_pelo_mesmo_endereco() -> None:
    """O `--publicar` copia byte a byte: o endereço único tem de valer das duas casas."""
    for n in NUMEROS:
        (a,) = sorted(MOCKUP.glob(f"{n}-*.html"))
        b = PUBLICADO / a.name
        assert faces_de(a.read_text(encoding="utf-8")) == faces_de(b.read_text(encoding="utf-8"))
        for _familia, enderecos in faces_de(a.read_text(encoding="utf-8")):
            for e in enderecos:
                assert (a.parent / e).resolve() == (b.parent / e).resolve()


def test_a_licenca_e_a_origem_moram_ao_lado_das_fontes() -> None:
    for licenca in ("OFL-SpaceGrotesk.txt", "OFL-JetBrainsMono.txt"):
        texto = (FONTES / licenca).read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE Version 1.1" in texto, licenca
    origem = (FONTES / "ORIGEM.md").read_text(encoding="utf-8")
    soma = {nome: lido for lido, nome in re.findall(r"^([0-9a-f]{64})  (\S+\.ttf)$", origem, re.M)}
    assert set(soma) == {"SpaceGrotesk-wght.ttf", "JetBrainsMono-wght.ttf"}
    for nome, esperada in soma.items():
        assert hashlib.sha256((FONTES / nome).read_bytes()).hexdigest() == esperada, (
            f"{nome} mudou e a ORIGEM.md não foi atualizada"
        )
    for versao in ("2.000", "2.211"):
        assert versao in origem


def test_o_wheel_leva_a_pasta_das_fontes() -> None:
    """O wheel nasce do pacote inteiro (`packages`); a pasta das fontes não é ignorada pelo git."""
    pyproject = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^packages = \["src/hefesto_dualsense4unix"\]', pyproject, re.M)
    verificar = subprocess.run(
        ["git", "check-ignore", *[str(p) for p in sorted(FONTES.iterdir())]],
        cwd=RAIZ, capture_output=True, check=False,
    )
    assert verificar.returncode == 1, (
        f"a pasta das fontes tem arquivo no .gitignore: {verificar.stdout.decode()}"
    )


def test_o_endereco_do_mockup_e_um_link_para_a_pasta_do_pacote() -> None:
    """De `mockup/`, `../assets/fontes/` é a raiz `assets/fontes`: um link relativo, não cópia."""
    link = RAIZ / "assets" / "fontes"
    assert link.is_symlink(), "assets/fontes deixou de ser link: há duas cópias das fontes"
    assert not os.path.isabs(os.readlink(link)), os.readlink(link)
    assert link.resolve() == FONTES.resolve()


def test_o_deb_nao_leva_o_link_do_mockup_quebrado(tmp_path: pathlib.Path) -> None:
    """O `.deb` copia `assets/` inteiro (`cp -r`, que copia o link como link) e não leva o `src/`:
    sem a limpeza, `/usr/share/.../assets/fontes` apontaria para nada. Roda o bloco do próprio
    `build_deb.sh`, do `cp` até a primeira linha em branco.

    Prova da D-2310-O-PACOTE-NAO-LEVA-LINK-QUE-NAO-RESOLVE.
    """
    linhas = (RAIZ / "scripts" / "build_deb.sh").read_text(encoding="utf-8").splitlines()
    (inicio,) = [i for i, ln in enumerate(linhas) if ln.startswith("cp -r assets/. ")]
    fim = linhas.index("", inicio)
    bloco = "\n".join(linhas[inicio:fim])
    destino = tmp_path / "usr" / "share" / "hefesto-dualsense4unix" / "assets"
    destino.mkdir(parents=True)
    subprocess.run(["bash", "-euc", bloco], cwd=RAIZ, check=True,
                   env={**os.environ, "STAGING": str(tmp_path)})
    quebrados = [str(p) for p in destino.rglob("*") if p.is_symlink() and not p.exists()]
    assert quebrados == [], f"o .deb levaria link quebrado: {quebrados}"
    assert (destino / "71-uinput.rules").is_file(), "o bloco deixou de copiar os assets"


_FILHO = r"""
import json, pathlib, sys
raiz, alvo, prazo = sys.argv[1], pathlib.Path(sys.argv[2]), float(sys.argv[3])
sys.path.insert(0, raiz + "/scripts")
import regua_de_tela
try:
    t = regua_de_tela.Tela(alvo, titulo_esperado="Hefesto", prazo=prazo)
except regua_de_tela.CargaFalhou as erro:
    print(json.dumps({"abriu": False, "erro": str(erro)[:300]}))
    raise SystemExit(0)
leitura = ("JSON.stringify([performance.getEntriesByType('navigation')[0].loadEventEnd,"
           " document.readyState])")
t.esperar_ate(lambda: json.loads(t.executar(leitura))[0] > 0, prazo=5.0, motivo="o evento load")
t.esperar_ate(
    lambda: all(f[1] in ("loaded", "error") for f in json.loads(t.executar(
        "JSON.stringify(Array.from(document.fonts).map(f => [f.family, f.status]))"
    )) if f[0].strip('"') == "Space Grotesk"),
    prazo=5.0, motivo="a Space Grotesk",
)
carga_ms, estado = json.loads(t.executar(leitura))
fontes = json.loads(t.executar(
    "JSON.stringify(Array.from(document.fonts).map(f => [f.family, f.status]))"))
print(json.dumps({"abriu": True, "estado": estado, "carga_ms": carga_ms,
                  "fontes": {f[0].strip('"'): f[1] for f in fontes}}))
t.fechar()
"""


def _abrir_sem_rede(pagina: pathlib.Path, prazo: float) -> dict[str, object]:
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    ambiente = {
        **os.environ,
        "https_proxy": REDE_MUDA, "http_proxy": REDE_MUDA,
        "HTTPS_PROXY": REDE_MUDA, "HTTP_PROXY": REDE_MUDA,
        "PYTHONPATH": str(RAIZ / "src"),
    }
    for nome in ("no_proxy", "NO_PROXY", "all_proxy", "ALL_PROXY"):
        ambiente.pop(nome, None)
    saida = subprocess.run(
        [sys.executable, "-c", _FILHO, str(RAIZ), str(pagina), str(prazo)],
        env=ambiente, capture_output=True, text=True, timeout=90, check=False,
    )
    linhas = [ln for ln in saida.stdout.splitlines() if ln.startswith("{")]
    assert linhas, f"o filho não respondeu (rc={saida.returncode}): {saida.stderr[-600:]}"
    resposta: dict[str, object] = json.loads(linhas[-1])
    return resposta


@pytest.mark.parametrize("raiz", [MOCKUP, PUBLICADO], ids=["mockup", "publicado"])
@pytest.mark.parametrize("aba", ["02", "10"])
def test_com_a_rede_muda_a_pagina_abre_em_menos_de_3s_e_a_fonte_carrega(
    raiz: pathlib.Path, aba: str,
) -> None:
    (pagina,) = sorted(raiz.glob(f"{aba}-*.html"))
    r = _abrir_sem_rede(pagina, prazo=10.0)
    assert r["abriu"] is True, f"{_id(pagina)} não chegou ao complete com a rede muda: {r}"
    assert r["estado"] == "complete"
    assert isinstance(r["carga_ms"], (int, float)) and r["carga_ms"] < 3000, (
        f"{_id(pagina)}: o load levou {r['carga_ms']} ms com a rede muda"
    )
    fontes = r["fontes"]
    assert isinstance(fontes, dict)
    assert fontes.get("Space Grotesk") == "loaded", f"a Space Grotesk não carregou: {fontes}"
    mono = fontes.get("JetBrains Mono")
    assert mono in {"loaded", "unloaded"}, f"a JetBrains Mono falhou: {fontes}"



def _as_duas_no_webkit(arq: pathlib.Path) -> dict[str, object]:
    r = _abrir_sem_rede(arq, prazo=10.0)
    assert r["abriu"] is True, f"{arq.name} não chegou ao complete com a rede muda: {r}"
    fontes = r["fontes"]
    assert isinstance(fontes, dict)
    return fontes


@pytest.mark.parametrize("arq", _de_fora(MOCKUP), ids=_id)
def test_a_pagina_de_fora_carrega_a_letra_da_casa_no_webkit(arq: pathlib.Path) -> None:
    fontes = _as_duas_no_webkit(arq)
    assert fontes.get("Space Grotesk") == "loaded", f"{_id(arq)}: {fontes}"
    assert fontes.get("JetBrains Mono") == "loaded", f"{_id(arq)}: {fontes}"


def test_a_mordida_sem_o_font_face_a_pagina_de_fora_nao_carrega_a_letra(
    tmp_path: pathlib.Path,
) -> None:
    """A régua de cima só vale se reprova quando a página volta a não embutir a letra."""
    original = MOCKUP / "calibrar-sensores.html"
    texto = original.read_text(encoding="utf-8")
    sem = re.sub(r"@font-face\s*\{[^}]*\}", "", texto)
    assert sem != texto, "a mordida não achou o @font-face"
    paginas = {}
    for nome, conteudo in (("mordida", sem), ("controle", texto)):
        (tmp_path / nome / "mockup").mkdir(parents=True)
        (tmp_path / nome / "assets").symlink_to(RAIZ / "assets")
        paginas[nome] = tmp_path / nome / "mockup" / original.name
        paginas[nome].write_text(conteudo, encoding="utf-8")
    fontes = _as_duas_no_webkit(paginas["mordida"])
    assert fontes.get("Space Grotesk") != "loaded", f"sem o @font-face a letra carregou: {fontes}"
    fontes = _as_duas_no_webkit(paginas["controle"])
    assert fontes.get("Space Grotesk") == "loaded", f"a cópia intacta não carregou: {fontes}"

def test_a_mordida_com_o_link_do_google_de_volta_a_pagina_nao_abre(tmp_path: pathlib.Path) -> None:
    """A régua de cima só vale se reprova quando a causa volta: o `<link>` trava o `complete`."""
    (original,) = sorted(MOCKUP.glob("02-*.html"))
    google = (
        '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700'
        '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
    )
    texto = original.read_text(encoding="utf-8")
    assert recursos_de_fora(texto) == []
    mordido = tmp_path / original.name
    mordido.write_text(texto.replace("<style>", google + "\n<style>", 1), encoding="utf-8")
    assert recursos_de_fora(mordido.read_text(encoding="utf-8")), "a mordida não pôs o link"
    r = _abrir_sem_rede(mordido, prazo=5.0)
    assert r["abriu"] is False, f"com o link do Google a página abriu com a rede muda: {r}"
    controle = tmp_path / "controle" / original.name
    controle.parent.mkdir()
    controle.write_text(texto, encoding="utf-8")
    r = _abrir_sem_rede(controle, prazo=5.0)
    assert r["abriu"] is True, f"a cópia sem o link não abriu: a mordida mede outra coisa {r}"
