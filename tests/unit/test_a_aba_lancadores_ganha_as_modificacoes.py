"""A aba Lançadores (Experimental no desenho do todo) ganha as modificações.

O quadro «Extensões» traz uma linha por modificação instalada (Kyty e Lovense), cada uma com a
chave de ligar, a engrenagem das configurações e o menu «⋮»; o quadro «Lançadores» fica com as
filas. A instalação é de um endereço ou de uma pasta. A Lovense é UMA extensão com três jeitos de
ligar, e o contador «N de 3 ligadas» acompanha as chaves da janela. Os impedimentos da Steam moram
na janela de configurar o lançador, e não em aviso fixo na aba.

Só o desenho (`mockup/07-lancadores.html`); a segunda passagem liga o produto.

MORDIDAS (executadas aqui, sobre uma cópia do HTML): tirar a engrenagem de uma linha, o «⋮», o
campo do endereço, ou devolver o aviso fixo da Steam reprova a régua; o contador que não reage ao
clique reprova no Chrome.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "07-lancadores.html"
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
CHROME = pathlib.Path("/usr/bin/google-chrome")
LARGURAS = ((1212, 809), (1918, 840), (1212, 740))


def _doc(texto: str | None = None) -> str:
    """O desenho sem estilo e sem script: o que a pessoa vê e o que ela aciona."""
    bruto = texto if texto is not None else MOCKUP.read_text(encoding="utf-8")
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", bruto, flags=re.S)


def _problemas(doc: str) -> list[str]:
    """O que falta ao quadro das extensões. Vazio quando a forma do desenho está inteira."""
    falta: list[str] = []
    quadro = re.search(r'<label class="quadro-titulo"[^>]*>Extensões</label>(.*?)'
                       r'<div class="quadro estica">', doc, flags=re.S)
    if not quadro:
        return ["sem o quadro «Extensões» antes do quadro dos lançadores"]
    corpo = quadro.group(1)
    linhas = re.split(r'(?=<div class="ext" data-modificacao=)', corpo)[1:]
    chaves = [re.search(r'data-modificacao="([^"]+)"', x).group(1) for x in linhas]
    if chaves != ["kyty", "lovense"]:
        falta.append(f"linhas de extensão {chaves}, e o desenho tem kyty e lovense")
    for chave, linha in zip(chaves, linhas, strict=False):
        for gesto, rotulo in (("ligar-modificacao", "a chave"),
                              ("configurar-modificacao", "a engrenagem"),
                              ("mais-da-modificacao", "o «⋮»")):
            if f'data-gesto="{gesto}" data-v="{chave}"' not in linha:
                falta.append(f"{chave}: sem {rotulo}")
        faz = re.search(r'<span class="ext-faz" data-dica="([^"]*)">([^<]*)</span>', linha)
        if not faz or faz.group(1) != faz.group(2):
            falta.append(f"{chave}: o «o que faz» não é igual à dica")
    instalar = re.search(r'<div class="ext-instalar.*?</div>', corpo, flags=re.S)
    if not instalar:
        falta.append("sem a linha «Instalar de um endereço»")
    else:
        for marca in ('data-linha="mod-endereco"', 'data-gesto="escolher-arquivo-da-modificacao"',
                      'data-gesto="instalar-modificacao"'):
            if marca not in instalar.group(0):
                falta.append(f"a instalação perdeu {marca}")
    if "class=\"ajuda" in doc:
        falta.append("um «?» voltou; a dica mora no data-dica")
    if re.search(r'class="[^"]*\b(aviso|lanc-aviso)\b', doc):
        falta.append("um aviso fixo voltou à aba; os impedimentos moram em «Configurar»")
    return falta


def test_o_quadro_das_extensoes_traz_kyty_e_lovense_com_as_tres_acoes() -> None:
    assert _problemas(_doc()) == []


def test_a_regua_morde_a_engrenagem_o_mais_o_endereco_e_o_aviso() -> None:
    doc = _doc()
    sem_engrenagem = doc.replace('data-gesto="configurar-modificacao" data-v="kyty"', 'data-x="1"')
    assert any("kyty: sem a engrenagem" in p for p in _problemas(sem_engrenagem))
    sem_mais = doc.replace('data-gesto="mais-da-modificacao" data-v="lovense"', 'data-x="1"')
    assert any("lovense: sem o «⋮»" in p for p in _problemas(sem_mais))
    sem_endereco = doc.replace('data-linha="mod-endereco"', 'data-x="1"')
    assert any("mod-endereco" in p for p in _problemas(sem_endereco))
    com_aviso = doc.replace('<div class="quadro estica">',
                            '<div class="aviso">x</div><div class="quadro estica">', 1)
    assert any("aviso fixo" in p for p in _problemas(com_aviso))
    sem_faz = doc.replace('<span class="ext-faz" data-dica="Jogos do Kyty',
                          '<span class="ext-faz" data-dica="Outra', 1)
    assert any("kyty" in p and "igual à dica" in p for p in _problemas(sem_faz))


def test_os_impedimentos_da_steam_moram_na_janela_de_configurar() -> None:
    """A fila da Steam não carrega aviso; o caminho é «Configurar», depois «Ver e resolver»."""
    doc = _doc()
    conf = doc[doc.index('id="lanc-conf"'):]
    linha = re.search(r"<span>Impedimentos</span>.*?</div>", conf, flags=re.S)
    assert linha, "a janela de configurar não tem a linha «Impedimentos»"
    assert 'href="#impedimentos"' in linha.group(0) and "Ver e resolver" in linha.group(0)
    fila = re.search(r'<div class="lanc-fila">.*?<div class="lf ausente"', doc, flags=re.S).group(0)
    assert "impedimento" not in fila.lower(), "a fila da Steam voltou a avisar do impedimento"


def test_a_lovense_e_uma_extensao_com_tres_jeitos_de_ligar() -> None:
    doc = _doc()
    janela = doc[doc.index('id="lovense"'):doc.index('id="impedimentos"')]
    jeitos = re.findall(r'<div class="lv-linha" data-modificacao="([^"]+)"', janela)
    assert jeitos == ["intiface", "lovense-celular", "buttplug"], jeitos
    for jeito in jeitos:
        assert f'data-gesto="ligar-modificacao" data-v="{jeito}"' in janela, jeito
        assert f'data-gesto="configurar-modificacao" data-v="{jeito}"' in janela, jeito
    assert "2 de 3 ligadas" in doc


def test_o_gerador_confere_o_proprio_desenho() -> None:
    """`aba07.py --conferir` roda só a régua de identidade: nenhuma cor de aparelho cravada."""
    r = subprocess.run([sys.executable, str(INTERFACE / "aba07.py"), "--conferir", str(MOCKUP)],
                       capture_output=True, text=True, cwd=str(INTERFACE), check=False)
    assert r.returncode == 0, r.stderr + r.stdout


@pytest.fixture(scope="module")
def navegador():
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        yield nav
        nav.close()


@pytest.mark.parametrize(("larg", "alt"), LARGURAS)
def test_a_aba_e_as_janelas_da_lovense_cabem_sem_rolagem_vertical(navegador, larg, alt) -> None:
    pg = navegador.new_page(viewport={"width": larg, "height": alt})
    try:
        pg.goto(MOCKUP.as_uri())
        m = pg.evaluate("""() => { const d = document.documentElement;
          return {alto: d.scrollHeight, cabe: d.clientHeight,
                  largo: d.scrollWidth > d.clientWidth + 1}; }""")
        assert m["alto"] <= m["cabe"] + 1 and not m["largo"], ("aba", m)
        for ancora in ("lovense", "lanc-conf", "impedimentos"):
            pg.goto(f"{MOCKUP.as_uri()}#{ancora}")
            dentro = pg.evaluate("""(a) => { const r = document.getElementById(a);
              const cx = r.querySelector('.tn-cx').getBoundingClientRect();
              const roladores = [r, ...r.querySelectorAll('*')].filter(e =>
                e.scrollHeight > e.clientHeight + 1 && e.clientHeight > 0 &&
                ['auto', 'scroll'].includes(getComputedStyle(e).overflowY)).length;
              return {topo: cx.top, fundo: cx.bottom, alto: innerHeight, roladores}; }""", ancora)
            assert dentro["topo"] >= 0 and dentro["fundo"] <= dentro["alto"] + 1, (ancora, dentro)
            assert dentro["roladores"] == 0, (ancora, dentro)
    finally:
        pg.close()


def test_o_contador_da_lovense_acompanha_as_chaves(navegador) -> None:
    """Ligar o terceiro jeito leva a «3 de 3 ligadas»; desligar todos desliga a extensão."""
    pg = navegador.new_page(viewport={"width": 1212, "height": 809})
    try:
        pg.goto(MOCKUP.as_uri())
        conta = "[data-lv-conta]"
        assert pg.inner_text(conta).strip() == "2 de 3 ligadas"
        pg.goto(f"{MOCKUP.as_uri()}#lovense")
        pg.click('#lovense .lv-linha[data-modificacao="buttplug"] .nj-tog')
        pg.goto(MOCKUP.as_uri() + "#")
        assert pg.inner_text(conta).strip() == "3 de 3 ligadas"
        for jeito in ("intiface", "lovense-celular", "buttplug"):
            pg.goto(f"{MOCKUP.as_uri()}#lovense")
            pg.click(f'#lovense .lv-linha[data-modificacao="{jeito}"] .nj-tog')
        assert pg.inner_text(conta).strip() == "0 de 3 ligadas"
        chave = pg.evaluate(
            "document.querySelector('.ext[data-modificacao=lovense] > .nj-tog').className")
        assert "ligado" not in chave, chave
    finally:
        pg.close()


# -- O produto: o pacote liga a aba ao registro das modificações ---------------------------------
#
# Tudo em ``tmp_path``: o registro, o código, os dados e a pasta de origem são de mentira, e a Steam
# é um dublê da sondagem. Nada toca o ``~/.config`` nem o ``~/.local`` dela.

import json
import shutil


def _a07():
    sys.path.insert(0, str(INTERFACE))
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


@pytest.fixture
def lar(tmp_path, monkeypatch):
    """O lar de mentira das modificações, e o pacote com o cache e as janelas zerados."""
    from hefesto_dualsense4unix.mods.instalador import Lugares

    lg = Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # noqa-acento: campo
                 registro=tmp_path / "config" / "mods.json",
                 estado=tmp_path / "run" / "mods-estado.json")
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lg))
    a07 = _a07()
    monkeypatch.setattr(a07.VIGIA, "_disparar", lambda: None)
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()
    a07._ESCOLHA.limpar()
    yield lg
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()
    a07._ESCOLHA.limpar()


@pytest.fixture
def ctx():
    sys.path.insert(0, str(INTERFACE))
    import pacotes

    return pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})


def _fonte(tmp_path: pathlib.Path, mod_id: str = "toque", *, nome: str = "Toque",
           permissoes: tuple[str, ...] = (), opcoes: list | None = None,
           extra: dict | None = None) -> pathlib.Path:
    """A pasta de uma extensão de tema (só declaração: nenhum processo)."""
    pasta = tmp_path / "fonte" / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto = {"id": mod_id, "nome": nome, "versao": "0.1", "api": ">=1,<2",  # noqa-acento: chave
                 "licenca": "MIT", "tipos": ["tema"], "tema": {},  # noqa-acento: chave
                 "permissoes": list(permissoes),  # noqa-acento: chave do manifesto
                 "descricao": "Muda um detalhe.",  # noqa-acento: chave
                 "opcoes": opcoes or [], **(extra or {})}  # noqa-acento: chave do manifesto
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return pasta


class _Ponte:
    """O ``p`` do gesto: o seletor de arquivo devolve o que o teste mandar."""

    def __init__(self, escolha: str | None = None) -> None:
        self.escolha = escolha

    def escolher_arquivo(self, titulo: str, padrao: str = "", sugestao: str = "") -> str | None:
        return self.escolha


def _instalar(a07, ctx, pasta: pathlib.Path) -> dict:
    return a07.instalar_modificacao(ctx, {"forma": {"mod-endereco": str(pasta)}}, _Ponte())


def _entrada(lar, mod_id: str):
    from hefesto_dualsense4unix.mods.instalador import ler_registro

    return ler_registro(lar.registro).get(mod_id)


def test_instalar_pelo_endereco_nao_liga_e_pinta_a_linha(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    carga = _instalar(a07, ctx, _fonte(tmp_path))
    assert "Toque instalada" in carga["recado"]
    entrada = _entrada(lar, "toque")
    assert entrada is not None and entrada.ligada is False, "instalar ligou sozinha"
    assert 'data-modificacao="toque"' in carga["blocos"][".ext-lista"]
    assert carga["mesa"]["mod-conta"] == "1 instalada"


def test_instalar_sem_endereco_recusa_dizendo(lar, ctx) -> None:
    a07 = _a07()
    with pytest.raises(RuntimeError, match="Digite o endereço"):
        a07.instalar_modificacao(ctx, {"forma": {"mod-endereco": "   "}}, _Ponte())
    assert _entrada(lar, "toque") is None


def test_escolher_a_pasta_instala_o_manifesto_apontado(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    pasta = _fonte(tmp_path)
    carga = a07.escolher_arquivo_da_modificacao(
        ctx, {}, _Ponte(str(pasta / "hefesto-mod.json")))
    assert "Toque instalada" in carga["recado"] and _entrada(lar, "toque") is not None
    # cancelar não é erro: a tela não fala
    assert a07.escolher_arquivo_da_modificacao(ctx, {}, _Ponte(None)) is None
    # outro arquivo não é o manifesto
    with pytest.raises(RuntimeError, match=r"hefesto-mod\.json"):
        a07.escolher_arquivo_da_modificacao(ctx, {}, _Ponte(str(pasta / "LEIA.txt")))


def test_a_recusa_da_infra_chega_como_frase(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    with pytest.raises(RuntimeError, match="não baixou"):
        _instalar(a07, ctx, tmp_path / "nao-existe")


def test_o_nome_de_terceiros_vai_escapado_para_a_linha(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    carga = _instalar(a07, ctx, _fonte(tmp_path, nome="<b>Ops</b>"))
    html = carga["blocos"][".ext-lista"]
    assert "<b>Ops</b>" not in html and "&lt;b&gt;Ops" in html


def test_ligar_com_permissao_nova_mostra_antes_e_liga_no_segundo(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, permissoes=("rede:local",)))
    primeiro = a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    # o recado não chega à tela: a lista aparece no ⋮ aberto da linha, e o clique só armou
    assert primeiro.get("armou") is True and "recado" not in primeiro
    assert "Usar a rede desta casa" in primeiro["blocos"][".ext-lista"]
    assert _entrada(lar, "toque").ligada is False, "ligou sem o «sim»"
    segundo = a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert "ligada" in segundo["recado"] and _entrada(lar, "toque").ligada is True
    assert "data-menu=" not in segundo["blocos"][".ext-lista"]
    terceiro = a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert "desligada" in terceiro["recado"] and _entrada(lar, "toque").ligada is False


def test_ligar_sem_permissao_nova_liga_no_primeiro_clique(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path))
    a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert _entrada(lar, "toque").ligada is True


def test_ligar_o_que_nao_esta_instalado_recusa(lar, ctx) -> None:
    with pytest.raises(RuntimeError, match="não está instalada"):
        _a07().ligar_modificacao(ctx, {"v": "fantasma"}, _Ponte())
    with pytest.raises(ValueError, match="de qual extensão"):
        _a07().ligar_modificacao(ctx, {}, _Ponte())


_OPCOES = [
    {"id": "quando", "rotulo": "Quando", "tipo": "escolha",
     "escolhas": ["Sempre", "Nunca"], "padrao": "Sempre"},  # noqa-acento: chave
    {"id": "avisar", "rotulo": "Avisar", "tipo": "ligado"},
    {"id": "teto", "rotulo": "Teto", "tipo": "numero", "padrao": 50},  # noqa-acento: chave
]


def test_a_janela_da_extensao_traz_o_valor_de_agora_de_cada_opcao(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, opcoes=_OPCOES))
    carga = a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte())
    janela = carga["blocos"]["#mod-janela"]
    assert "Configurar · Toque" in janela and "<select" in janela
    assert 'value="50"' in janela and "Nunca" in janela


def _guardado(lar) -> dict:
    arquivo = lar.dados / "toque" / "opcoes.json"
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}


def test_a_opcao_mudada_espera_o_guardar_e_o_guardar_grava(lar, ctx, tmp_path) -> None:
    """D-1910-A-JANELA-DA-EXTENSAO-GUARDA-NO-GUARDAR: a mudança é rascunho até o Guardar."""
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, opcoes=_OPCOES))
    a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte())
    carga = a07.guardar_opcao_da_modificacao(
        ctx, {"v": "toque:quando", "valor": "Nunca", "evento": "change"}, _Ponte())
    assert "<option selected>Nunca" in carga["blocos"]["#mod-janela"], "sem o rascunho na janela"
    assert _guardado(lar) == {}, "a opção gravou antes do Guardar"
    # o clique do select (o mesmo gesto dispara click e change) não muda nada
    assert a07.guardar_opcao_da_modificacao(
        ctx, {"v": "toque:quando", "valor": "Sempre", "evento": "click"}, _Ponte()) is None
    feito = a07.guardar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert feito["recado"] == "Guardado."
    assert _guardado(lar) == {"quando": "Nunca", "avisar": False, "teto": 50.0}
    assert "<option selected>Nunca" in feito["blocos"]["#mod-janela"]
    assert "recado" not in a07.guardar_modificacao(ctx, {"v": "toque"}, _Ponte()), (
        "o Guardar sem mudança disse que guardou")


def test_o_cancelar_joga_fora_o_rascunho(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, opcoes=_OPCOES))
    a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte())
    a07.guardar_opcao_da_modificacao(
        ctx, {"v": "toque:quando", "valor": "Nunca", "evento": "change"}, _Ponte())
    # o Cancelar é `href="#"`: fecha sem gesto, e a janela reaberta nasce do guardado
    janela = a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte())["blocos"]["#mod-janela"]
    assert "<option selected>Sempre" in janela
    a07.guardar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert _guardado(lar) == {}


def test_a_chave_de_ligado_vira_no_clique_e_o_numero_valida(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, opcoes=_OPCOES))
    a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte())
    a07.guardar_opcao_da_modificacao(ctx, {"v": "toque:avisar", "evento": "click"}, _Ponte())
    assert a07._MEXIDA.rascunho == {"avisar": True}
    a07.guardar_opcao_da_modificacao(ctx, {"v": "toque:avisar", "evento": "click"}, _Ponte())
    assert a07._MEXIDA.rascunho == {"avisar": False}, "o segundo clique não virou o rascunho"
    a07.guardar_opcao_da_modificacao(ctx, {"v": "toque:avisar", "evento": "click"}, _Ponte())
    a07.guardar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert _guardado(lar)["avisar"] is True
    with pytest.raises(RuntimeError, match="pede um número"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": "toque:teto", "valor": "muito", "evento": "change"}, _Ponte())
    with pytest.raises(RuntimeError, match="escolhas"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": "toque:quando", "valor": "Talvez", "evento": "change"}, _Ponte())
    with pytest.raises(RuntimeError, match="não tem essa opção"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": "toque:inventada", "valor": "x", "evento": "change"}, _Ponte())
    assert a07._MEXIDA.rascunho == {}, "a recusa entrou no rascunho"


def test_o_menu_abre_mostra_as_permissoes_e_fecha(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, permissoes=("rede:local",)))
    aberto = a07.mais_da_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert "Ver permissões" in aberto["blocos"][".ext-lista"]
    pedido = {"v": "toque:permissoes"}  # noqa-acento: chave
    com_permissoes = a07.mais_da_modificacao(ctx, pedido, _Ponte())
    assert "Usar a rede desta casa" in com_permissoes["blocos"][".ext-lista"]
    fechado = a07.mais_da_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert "data-menu=" not in fechado["blocos"][".ext-lista"]


def test_remover_pede_o_segundo_clique_e_apaga_o_codigo_e_os_dados(lar, ctx, tmp_path) -> None:
    # D-1810-O-SIM-DAS-PERMISSOES-E-O-REMOVER-SE-CONFIRMAM-NO-MENU-DA-LINHA
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, opcoes=_OPCOES))
    a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte())
    a07.guardar_opcao_da_modificacao(
        ctx, {"v": "toque:avisar", "evento": "click"}, _Ponte())
    a07.guardar_modificacao(ctx, {"v": "toque"}, _Ponte())
    primeiro = a07.mais_da_modificacao(ctx, {"v": "toque:remover"}, _Ponte())
    assert primeiro.get("armou") is True and "recado" not in primeiro
    assert "Confirmar remoção" in primeiro["blocos"][".ext-lista"]
    assert _entrada(lar, "toque") is not None, "removeu no primeiro clique"
    segundo = a07.mais_da_modificacao(ctx, {"v": "toque:remover"}, _Ponte())
    assert segundo["recado"] == "Toque removida."
    assert _entrada(lar, "toque") is None
    assert not (lar.codigo / "toque").exists() and not (lar.dados / "toque").exists()
    assert "Nenhuma extensão instalada" in segundo["blocos"][".ext-lista"]


def test_atualizar_baixa_de_novo_do_endereco_gravado(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    pasta = _fonte(tmp_path)
    _instalar(a07, ctx, pasta)
    manifesto = json.loads((pasta / "hefesto-mod.json").read_text(encoding="utf-8"))
    manifesto["versao"] = "0.2"  # noqa-acento: chave
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    feito = a07.mais_da_modificacao(ctx, {"v": "toque:atualizar"}, _Ponte())
    assert "atualizada para a versão 0.2" in feito["recado"]
    assert _entrada(lar, "toque").versao == "0.2"
    shutil.rmtree(pasta)


def test_acao_inventada_do_menu_recusa(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path))
    with pytest.raises(RuntimeError, match="não existe"):
        a07.mais_da_modificacao(ctx, {"v": "toque:formatar"}, _Ponte())


# -- A Steam: os impedimentos ----------------------------------------------------------------------


def _dois_impedimentos():
    from hefesto_dualsense4unix.integrations import impedimentos_da_steam as imp

    return (imp.Impedimento("111", "Jogo Um", imp.ENTRADA),
            imp.Impedimento("222", "Jogo Dois", imp.PROTON))


def test_ver_impedimentos_sonda_e_lista_uma_linha_por_jogo(lar, ctx, monkeypatch) -> None:
    a07 = _a07()
    monkeypatch.setattr(a07, "_sondar_a_steam", _dois_impedimentos)
    carga = a07.ver_impedimentos(ctx, {"v": "steam"}, _Ponte())
    janela = carga["blocos"]["#imp-janela"]
    assert "Jogo Um" in janela and "Jogo Dois" in janela and "2 jogos com impedimento" in janela
    assert 'data-v="entrada:111"' in janela and 'data-v="proton:222"' in janela
    with pytest.raises(RuntimeError, match="Só a Steam"):
        a07.ver_impedimentos(ctx, {"v": "heroic"}, _Ponte())


def test_resolver_um_cura_so_aquele_jogo_e_repinta(lar, ctx, monkeypatch) -> None:
    from hefesto_dualsense4unix.integrations import impedimentos_da_steam as imp

    a07 = _a07()
    restam = list(_dois_impedimentos())
    curados: list[list[str]] = []
    monkeypatch.setattr(a07, "_sondar_a_steam", lambda: tuple(restam))

    def curar(alvo, *, home=None):
        curados.append([i.chave for i in alvo])
        for i in alvo:
            restam.remove(i)
        return "Resolvido: Jogo Um."

    monkeypatch.setattr(imp, "curar", curar)
    a07.ver_impedimentos(ctx, {"v": "steam"}, _Ponte())
    carga = a07.resolver_impedimento(ctx, {"v": "entrada:111"}, _Ponte())
    assert curados == [["entrada:111"]], "curou mais do que o jogo clicado"
    assert carga["recado"] == "Resolvido: Jogo Um."
    assert "Jogo Um" not in carga["blocos"]["#imp-janela"]
    assert "Jogo Dois" in carga["blocos"]["#imp-janela"]


def test_resolver_todos_cura_a_lista_inteira(lar, ctx, monkeypatch) -> None:
    from hefesto_dualsense4unix.integrations import impedimentos_da_steam as imp

    a07 = _a07()
    restam = list(_dois_impedimentos())
    curados: list[list[str]] = []
    monkeypatch.setattr(a07, "_sondar_a_steam", lambda: tuple(restam))

    def curar(alvo, *, home=None):
        curados.append([i.chave for i in alvo])
        restam.clear()
        return "Resolvido."

    monkeypatch.setattr(imp, "curar", curar)
    carga = a07.resolver_todos_os_impedimentos(ctx, {}, _Ponte())
    assert curados == [["entrada:111", "proton:222"]]
    assert "Nenhum jogo com impedimento" in carga["blocos"]["#imp-janela"]


def test_com_a_steam_aberta_a_cura_recusa_dizendo(lar, ctx, monkeypatch) -> None:
    from hefesto_dualsense4unix.integrations import impedimentos_da_steam as imp
    from hefesto_dualsense4unix.integrations import steam_input_ponte as sip

    a07 = _a07()
    monkeypatch.setattr(a07, "_sondar_a_steam", _dois_impedimentos)
    monkeypatch.setattr(imp, "_com_o_steam_input_ligado", lambda home: ["111"])
    monkeypatch.setattr(sip, "ler_allowlist", lambda: [])
    monkeypatch.setattr(sip, "garantir_fora_da_lista_desligado",
                        lambda home, **kw: ("steam_aberta", []))
    with pytest.raises(RuntimeError, match="Feche a Steam"):
        a07.resolver_impedimento(ctx, {"v": "entrada:111"}, _Ponte())


def test_o_impedimento_que_ja_foi_resolvido_nao_vira_cura_cega(lar, ctx, monkeypatch) -> None:
    a07 = _a07()
    monkeypatch.setattr(a07, "_sondar_a_steam", lambda: ())
    with pytest.raises(RuntimeError, match="já foi resolvido"):
        a07.resolver_impedimento(ctx, {"v": "entrada:111"}, _Ponte())


def test_a_sondagem_nunca_levanta_e_nomeia_o_jogo(monkeypatch) -> None:
    from hefesto_dualsense4unix.integrations import impedimentos_da_steam as imp

    def estoura(home):
        raise OSError("sem vdf")

    monkeypatch.setattr(imp, "_com_o_steam_input_ligado", estoura)
    monkeypatch.setattr(imp, "_fora_do_proton_fixado", lambda home: ["222"])
    monkeypatch.setattr(imp, "_nome", lambda appid, home: f"Jogo {appid}")
    achados = imp.sondar(pathlib.Path("/nao/existe"))
    assert [(i.chave, i.jogo) for i in achados] == [("proton:222", "Jogo 222")]


# -- A janela de cada lançador e a escolha ---------------------------------------------------------


class _Seletor(_Ponte):
    """A ponte do «Configurar»: o seletor devolve o que o teste mandar e o declare anota."""

    def __init__(self, escolha: str | None = None) -> None:
        super().__init__(escolha)
        self.chamadas: list[dict] = []

    def machine_declare(self, maquina: dict) -> tuple[bool, None]:
        self.chamadas.append(maquina)
        return True, None


@pytest.fixture
def casa(tmp_path, monkeypatch) -> pathlib.Path:
    """``HOME`` e as pastas XDG no ``tmp``: a pasta de atalhos, a Steam e o ``maquina.json``."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local/share"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "usr/share"))
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    (tmp_path / ".local/share/applications").mkdir(parents=True)
    (tmp_path / "usr/share/applications").mkdir(parents=True)
    return tmp_path


def test_configurar_o_lancador_abre_a_janela_igual_para_todos(lar, ctx, casa, monkeypatch) -> None:
    """O arranjo de 19/10: «Escolher o arquivo…», as pastas, a chave, Cancelar e Guardar."""
    from hefesto_dualsense4unix.integrations import steam_launch_options

    a07 = _a07()
    monkeypatch.setattr(a07, "_sondar_a_steam", _dois_impedimentos)
    monkeypatch.setattr(steam_launch_options, "pastas_steamapps",
                        lambda home=None: [casa / "Jogos/SteamLibrary/steamapps"])
    steam = a07.configurar_lancador(ctx, {"v": "steam"}, _Ponte())
    janela = steam["blocos"]["#lanc-janela"]
    assert "Configurar · Steam" in janela and "Como entrou" in janela
    assert "2 jogos não recebem" in janela and 'data-gesto="ver-impedimentos"' in janela
    assert "<span>Pastas dos jogos</span>" in janela
    assert "<code>~/Jogos/SteamLibrary</code>" in janela
    assert 'data-gesto="escolher-o-lancador" data-v="steam">Escolher o arquivo…' in janela
    assert 'class="nj-tog ligado"' in janela and 'data-linha="perfil-por-jogo"' in janela
    rodape = janela.split('class="tn-rod"')[1]
    assert '<a class="btn" href="#">Cancelar</a>' in rodape
    assert 'data-gesto="guardar-lancador" data-hef-forma="lanc-janela" data-v="steam"' in rodape
    topo = janela.split('class="tn-corpo"')[0]
    assert 'class="ext-mais"' in topo and 'class="btn mini apagado"' in topo
    assert topo.count("data-gesto=") == 1, "o ⋮ de fábrica atualiza ou remove a Steam"
    assert 'class="ext-menu ext-pop"' in topo
    aberto = a07.mais_da_modificacao(ctx, {"v": "steam"}, _Ponte())["blocos"]["#lanc-janela"]
    assert 'class="ext-menu ext-pop aberto"' in aberto.split('class="tn-corpo"')[0]
    flatpak = a07.configurar_lancador(ctx, {"v": "flatpak"}, _Ponte())["blocos"]["#lanc-janela"]
    assert "ver-impedimentos" not in flatpak and "Pastas dos jogos" not in flatpak
    assert "perfil-por-jogo" not in flatpak, "o Flatpak não entrega jogo: a chave não liga nada"
    retroarch = a07.configurar_lancador(ctx, {"v": "retroarch"}, _Ponte())["blocos"]["#lanc-janela"]
    assert "perfil-por-jogo" in retroarch
    with pytest.raises(RuntimeError, match="Não conheço"):
        a07.configurar_lancador(ctx, {"v": "inventado"}, _Ponte())


def test_o_escolher_espera_o_guardar_e_o_guardar_grava_o_atalho_e_a_chave(
        lar, ctx, casa) -> None:
    """D-1910-O-ESCOLHER-DO-CONFIGURAR-APONTA-O-ATALHO e D-1910-CADA-JOGO-GANHA-O-PERFIL-..."""
    a07 = _a07()
    atalho = casa / ".local/share/applications/org.libretro.RetroArch.desktop"
    atalho.write_text("[Desktop Entry]\nName=RetroArch\n", encoding="utf-8")
    p = _Seletor(str(atalho))
    a07.configurar_lancador(ctx, {"v": "retroarch"}, p)
    carga = a07.escolher_o_lancador(ctx, {"v": "retroarch"}, p)
    assert ">~/.local/share/applications/org.libretro.RetroArch.desktop</code>" in (
        carga["blocos"]["#lanc-janela"])
    assert p.chamadas == [], "o «Escolher o arquivo…» gravou antes do Guardar"
    feito = a07.guardar_lancador(
        ctx, {"v": "retroarch", "forma": {"perfil-por-jogo": "Desligado"}}, p)
    assert p.chamadas[0] == {"lancadores": {"retroarch": {
        "rotulo": "RetroArch", "atalhos": ["org.libretro.RetroArch"]}}}, p.chamadas
    assert p.chamadas[1] == {"perfil_por_jogo": {"retroarch": False}}
    assert len(p.chamadas) == 2 and "recado" in feito
    assert a07._PARA_QUEM == "" and a07._MEXIDA.onde_escolhido == ""
    # a chave igual à guardada não escreve nada
    p.chamadas.clear()
    a07.guardar_lancador(ctx, {"v": "retroarch", "forma": {"perfil-por-jogo": "Ligado"}}, p)
    assert p.chamadas == []


def test_o_escolher_fora_das_pastas_recusa_e_o_cancelar_esquece(lar, ctx, casa) -> None:
    a07 = _a07()
    fora = casa / "Downloads/RetroArch.desktop"
    fora.parent.mkdir()
    fora.write_text("[Desktop Entry]\nName=RetroArch\n", encoding="utf-8")
    p = _Seletor(str(fora))
    a07.configurar_lancador(ctx, {"v": "retroarch"}, p)
    with pytest.raises(RuntimeError, match="fora das pastas"):
        a07.escolher_o_lancador(ctx, {"v": "retroarch"}, p)
    assert a07._MEXIDA.onde_escolhido == ""
    with pytest.raises(RuntimeError, match="Abra o «Configurar»"):
        a07.escolher_o_lancador(ctx, {"v": "lutris"}, p)
    dentro = casa / ".local/share/applications/RetroArch.desktop"
    dentro.write_text("[Desktop Entry]\nName=RetroArch\n", encoding="utf-8")
    p.escolha = str(dentro)
    a07.escolher_o_lancador(ctx, {"v": "retroarch"}, p)
    assert a07._MEXIDA.onde_escolhido == str(dentro)
    # o Cancelar é `href="#"`; a janela reaberta não traz o rascunho
    a07.configurar_lancador(ctx, {"v": "retroarch"}, p)
    assert a07._MEXIDA.onde_escolhido == ""
    a07.guardar_lancador(ctx, {"v": "retroarch", "forma": {}}, p)
    assert p.chamadas == []
    assert a07.escolher_o_lancador(ctx, {"v": "retroarch"}, _Seletor(None)) is None


def test_o_mais_do_configurar_e_o_da_extensao_e_some_com_ela(lar, ctx, monkeypatch) -> None:
    """D-1910-O-MAIS-DO-CONFIGURAR-ACENDE-SO-NA-EXTENSAO: o mesmo menu, nos dois lugares."""
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    html = exp.lanc_conf_miolo_html(exp.Conf(
        "kytyps5", "KytyPS5", "Como extensão", "", "", modificacao="kytyps5",
        menu=exp.menu_html("kytyps5", remover=True, fecha=True)))
    topo = html.split('class="tn-corpo"')[0]
    assert 'data-gesto="mais-da-modificacao" data-v="kytyps5"' in topo
    assert 'class="ext-menu ext-pop aberto"' in topo
    assert ('<a class="btn mini" href="#" data-gesto="mais-da-modificacao" '
            'data-v="kytyps5:remover">Confirmar remoção</a>') in topo, "a confirmação não fecha"
    assert "escolher-o-lancador" not in html, "onde ele está é a extensão quem diz"

    a07 = _a07()
    montadas: list[str] = []

    def montar(chave, state=None):
        montadas.append(chave)
        if len(montadas) > 1:
            raise RuntimeError("Não conheço esse lançador. Nada foi alterado.")

    monkeypatch.setattr(a07, "_montar_a_conf", montar)
    monkeypatch.setattr(a07, "_mexer_na_modificacao", lambda mod_id, acao: "Toque removida.")
    a07._MEXIDA.conf, a07._MEXIDA.conf_da_modificacao = "kytyps5", "toque"
    a07.mais_da_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert montadas == ["kytyps5"], "a janela aberta não acompanhou o ⋮"
    a07.mais_da_modificacao(ctx, {"v": "toque:remover"}, _Ponte())
    assert a07._MEXIDA.conf == "" and a07._MEXIDA.html_conf == ""
    a07._MEXIDA.conf, a07._MEXIDA.conf_da_modificacao = "steam", ""
    a07.mais_da_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert len(montadas) == 2, "o ⋮ de uma extensão repintou a janela da Steam"


def test_a_chave_desligada_tira_os_jogos_daquele_lancador_da_semeadura(
        casa, tmp_path, monkeypatch) -> None:
    """O jogo do lançador desligado não ganha perfil nem entra na marca: religar o semeia."""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
    from hefesto_dualsense4unix.integrations import jogos_locais
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, gravar_maquina

    assert censo.lancador_do_jogo("steam") == "steam"
    assert censo.lancador_do_jogo("desktop", "620") == "steam"
    assert censo.lancador_do_jogo("desktop", "") == ""
    assert censo.lancador_do_jogo("lutris") == "lutris"
    assert censo.lancador_do_jogo("mgba") == "emuladores"
    assert {"steam", "heroic", "lutris", "retroarch", "emuladores"} <= censo.LANCADORES_COM_JOGOS
    assert "flatpak" not in censo.LANCADORES_COM_JOGOS

    with pytest.raises(ValueError):
        gravar_maquina({"perfil_por_jogo": {"A Steam": False}})
    gravar_maquina({"perfil_por_jogo": {"lutris": False}})
    assert carregar_maquina().perfil_por_jogo == {"lutris": False}
    assert loader.lancadores_sem_perfil_por_jogo() == frozenset({"lutris"})

    jogos = [jogos_locais.JogoLocal("620", "Portal Dois", "steam"),
             jogos_locais.JogoLocal("", "Celeste", "lutris", lancador="Lutris", chave="celeste")]
    monkeypatch.setattr(jogos_locais, "jogos_da_biblioteca_steam", lambda home=None: jogos[:1])
    monkeypatch.setattr(jogos_locais, "jogos_com_janela", lambda home=None, pastas=None: jogos[1:])
    destino = tmp_path / "perfis"
    feito = loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    assert len(feito.criados) == 1 and len(feito.linhas) == 1, feito
    gravar_maquina({"perfil_por_jogo": {"lutris": True}})
    assert len(loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa).criados) == 1, (
        "religar a chave não semeou o jogo que ficou de fora")


def test_identificar_diz_o_que_achou_ou_como_ensinar(lar, ctx, monkeypatch) -> None:
    # D-1810-O-IDENTIFICAR-QUE-NAO-ACHA-PISCA-A-RECUSA
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

    a07 = _a07()
    achou = desenho.Leitura(onde_estao=(("flatpak", "/usr/bin/flatpak"), ("lutris", "")))
    monkeypatch.setattr(a07.VIGIA, "ler", lambda: achou)
    monkeypatch.setattr(a07.VIGIA, "esquecer", lambda: None)
    dito = a07.identificar_lancador(ctx, {"v": "flatpak"}, _Ponte())["recado"]
    assert dito.startswith("Achei Flatpak") and "/usr/bin/flatpak" in dito
    # O não achado sobe como recusa (o botão pisca a recusa); pelo recado, piscaria «deu certo».
    # MORDIDA: devolver a frase em `recado` deixa este `raises` sem exceção.
    with pytest.raises(RuntimeError, match=r"^Não achei Lutris.*Adicionar um lançador"):
        a07.identificar_lancador(ctx, {"v": "lutris"}, _Ponte())
    with pytest.raises(RuntimeError, match="Não conheço"):
        a07.identificar_lancador(ctx, {"v": "inventado"}, _Ponte())


def test_criar_perfil_do_jogo_marca_tem_perfil_e_mantem_a_janela(lar, ctx, monkeypatch) -> None:
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

    a07 = _a07()
    jogos = (desenho.JogoParaEscolher(chave="steam_app_1", nome="Um"),
             desenho.JogoParaEscolher(chave="steam_app_2", nome="Dois"))
    a07._ESCOLHA.modo, a07._ESCOLHA.lancador = desenho.CRIAR_PERFIL, "steam"
    a07._ESCOLHA.jogos = jogos
    feitos: list[str] = []
    com_perfil: set[str] = set()
    monkeypatch.setattr(a07, "_perfis_que_casam", lambda: (set(com_perfil), set()))

    def criar(ctx_, p, jogo):
        feitos.append(jogo.chave)
        com_perfil.add(jogo.chave)
        return f"Perfil de {jogo.nome} criado."

    monkeypatch.setattr(a07, "_criar_o_perfil_de", criar)
    carga = a07.criar_perfil_do_jogo(ctx, {"v": "steam_app_1"}, _Ponte())
    assert feitos == ["steam_app_1"] and carga["recado"] == "Perfil de Um criado."
    miolo = carga["blocos"]["#lanc-escolha"]
    assert miolo.count("Tem perfil") == 1 and 'data-v="steam_app_2"' in miolo
    assert 'data-v="steam_app_1"' not in miolo, "o jogo que ganhou perfil ainda oferece «Criar»"
    with pytest.raises(RuntimeError, match="não está mais na lista"):
        a07.criar_perfil_do_jogo(ctx, {"v": "steam_app_9"}, _Ponte())


# --- o contrato das peças da janela: grupos em abas, cor, «Agora» e «Parar tudo» (18/10/2026) -----

_EM_GRUPOS = [
    {"id": "teto", "rotulo": "Teto", "tipo": "numero", "grupo": "Segurança", "padrao": 50},  # noqa-acento: chave
    {"id": "gesto", "rotulo": "Gesto", "tipo": "ligado", "grupo": "Gestos"},  # noqa-acento: chave
    {"id": "luz", "rotulo": "Cor da luz", "tipo": "cor", "grupo": "Luz",  # noqa-acento: chave
     "padrao": "#00AAFF"},  # noqa-acento: chave
]


def _manifesto_de(**campos) -> object:
    from hefesto_dualsense4unix.mods.manifesto import Manifesto

    base = {"id": "toque", "nome": "Toque", "versao": "0.1", "api": ">=1,<2",  # noqa-acento: chave
            "licenca": "MIT", "tipos": ["tema"], "tema": {}}  # noqa-acento: chave
    return Manifesto.model_validate({**base, **campos})


def test_o_manifesto_aceita_grupo_cor_agora_e_parar_tudo() -> None:
    m = _manifesto_de(opcoes=_EM_GRUPOS, agora=["nivel", "perfil", "aparelhos"], parar_tudo=True,
                      permissoes=["ler:acessorios.gesto"])  # noqa-acento: chave
    assert [o.grupo for o in m.opcoes] == ["Segurança", "Gestos", "Luz"]  # noqa-acento: chave
    assert m.agora == ["nivel", "perfil", "aparelhos"] and m.parar_tudo is True


def test_o_manifesto_recusa_o_agora_e_o_parar_tudo_sem_a_permissao_do_retorno() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError, match=r"ler:acessorios\.gesto"):
        _manifesto_de(parar_tudo=True)
    with pytest.raises(pydantic.ValidationError, match=r"ler:acessorios\.gesto"):
        _manifesto_de(agora=["nivel"])
    with pytest.raises(pydantic.ValidationError):
        _manifesto_de(agora=["nivel", "nivel"], permissoes=["ler:acessorios.gesto"])  # noqa-acento: chave
    with pytest.raises(pydantic.ValidationError):
        _manifesto_de(agora=["temperatura"], permissoes=["ler:acessorios.gesto"])  # noqa-acento: chave


def test_a_opcao_de_cor_recusa_o_padrao_que_nao_e_hexa() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError, match="#rrggbb"):
        _manifesto_de(opcoes=[{"id": "luz", "rotulo": "Luz", "tipo": "cor", "padrao": "azul"}])  # noqa-acento: chave


def test_a_janela_com_tres_grupos_desenha_um_cartao_por_grupo_e_a_cor(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, opcoes=_EM_GRUPOS))
    janela = a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte())["blocos"]["#mod-janela"]
    titulos = re.findall(r'<span class="ac-tit">([^<]*)</span>', janela)
    assert titulos == ["Segurança", "Gestos", "Luz"], titulos  # noqa-acento: chave
    assert "mg-aba" not in janela and 'type="radio"' not in janela
    assert 'type="color"' in janela and 'value="#00aaff"' in janela  # o padrão, em minúsculas
    assert '<span class="ext-rot">Para</span>Todos' in janela.split('class="tn-corpo"')[0]
    rodape = janela.split('class="tn-rod"')[1]
    assert '<a class="btn" href="#">Cancelar</a>' in rodape
    assert 'data-gesto="guardar-modificacao" data-v="toque">Guardar</a>' in rodape


def test_um_grupo_so_desenha_um_cartao(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    unico = [{**o, "grupo": "Tudo"} for o in _OPCOES]
    _instalar(a07, ctx, _fonte(tmp_path, opcoes=unico))
    janela = a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte())["blocos"]["#mod-janela"]
    assert re.findall(r'<span class="ac-tit">([^<]*)</span>', janela) == ["Tudo"]
    assert "mg-aba" not in janela and "<select" in janela


def test_guardar_a_cor_valida_e_normaliza(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, opcoes=_EM_GRUPOS))
    a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte())
    carga = a07.guardar_opcao_da_modificacao(
        ctx, {"v": "toque:luz", "valor": "#FF8800", "evento": "change"}, _Ponte())
    assert 'value="#ff8800"' in carga["blocos"]["#mod-janela"]
    a07.guardar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert _guardado(lar)["luz"] == "#ff8800"
    with pytest.raises(RuntimeError, match="#rrggbb"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": "toque:luz", "valor": "vermelho", "evento": "change"}, _Ponte())


def test_a_linha_da_fila_so_leva_a_contagem_e_a_frase_do_cartao_velho_fica_fora() -> None:
    """A frase «Abra o Heroic uma vez…» passava por baixo dos três botões da linha."""
    # D-1810-A-LINHA-DO-LANCADOR-LEVA-SO-A-CONTAGEM
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import FRASE_NUNCA_ABERTO
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    a07 = _a07()

    def lanc(jogos: str, presente: bool = True) -> dl.Lancador:
        return dl.Lancador(chave="heroic", nome="Heroic", selo="", jogos=jogos, diz="",
                           presente=presente)

    assert a07._jogos_da_fila(lanc("22 jogos instalados")) == "22 jogos"
    assert a07._jogos_da_fila(lanc("1 jogo instalado")) == "1 jogo"
    assert a07._jogos_da_fila(lanc(FRASE_NUNCA_ABERTO.format(nome="Heroic"))) == ""
    assert a07._jogos_da_fila(lanc("22 jogos instalados", presente=False)) == ""
