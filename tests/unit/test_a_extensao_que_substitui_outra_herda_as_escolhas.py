"""A extensão que substitui outra herda as escolhas do usuário e a manda embora.

A sprint é a A-EXTENSAO-QUE-SUBSTITUI-OUTRA-HERDA-AS-ESCOLHAS-01. Duas extensões FALSAS, em
lugares de mentira no ``tmp_path``: o mecanismo é de qualquer extensão, e nenhum nome de
extensão real entra no código nem aqui.

MORDIDAS (22/10/2026, executadas sobre a cura e devolvidas):

- a herança das escolhas arrancada (``herdar`` que não copia nada) reprova
  ``test_a_escolha_que_a_nova_aceita_passa_e_a_que_nao_aceita_fica_no_padrao``;
- a remoção da antiga arrancada reprova ``test_a_antiga_sai_com_codigo_dados_e_registro``;
- o «sim» herdado (``permissoes_aceitas`` somadas às da antiga) reprova
  ``test_a_permissao_nova_continua_pedindo_o_sim``;
- a régua do ``substitui`` desligada reprova ``test_a_regua_recusa_o_que_nao_e_substituir``;
- o padrão que o ``guardar`` grava contado como escolha (``_escolhida`` = id no arquivo) reprova
  ``test_o_padrao_gravado_na_nova_nao_tapa_a_escolha_da_antiga``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador, opcoes
from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, Lugares
from hefesto_dualsense4unix.mods.manifesto import Manifesto

ANTIGA = "ponte-velha"
NOVA = "ponte-unica"

def _opcao(opcao_id: str, tipo: str, valor: Any, **mais: Any) -> dict[str, Any]:
    return {"id": opcao_id, "rotulo": opcao_id, "tipo": tipo,
            "padrao": valor, **mais}  # (noqa-acento)


OPCOES_DA_ANTIGA = [
    _opcao("porta", "numero", 20010),
    _opcao("modo", "escolha", "a", escolhas=["a", "b"]),
    _opcao("so_na_antiga", "ligado", False),
]
OPCOES_DA_NOVA = [
    _opcao("porta", "numero", 20010),
    _opcao("modo", "escolha", "a", escolhas=["a", "c"]),
    _opcao("so_na_nova", "ligado", True),
]


def _lugares(raiz: Path) -> Lugares:
    return Lugares(codigo=raiz / "codigo", dados=raiz / "dados",  # (noqa-acento)
                   registro=raiz / "mods.json", estado=raiz / "estado.json")


def _pasta(raiz: Path, mod_id: str, *, versao: str = "1.0.0",
           permissoes: tuple[str, ...] = ("ler:estado",),
           opcoes_: list[dict[str, Any]] | None = None,
           substitui: tuple[str, ...] = ()) -> Path:
    """A pasta-fonte de uma extensão de mentira, pronta para o ``instalar`` de pasta."""
    pasta = raiz / "fontes" / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "mod.py").write_text("import time\nwhile True:\n    time.sleep(1)\n", encoding="utf-8")
    manifesto: dict[str, Any] = {
        "id": mod_id, "nome": f"Extensão {mod_id}", "versao": versao,  # (noqa-acento)
        "api": ">=2,<3", "licenca": "MIT", "tipos": ["processo"],
        "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": list(permissoes),  # (noqa-acento)
        "opcoes": opcoes_ or [],  # (noqa-acento)
    }
    if substitui:
        manifesto["substitui"] = list(substitui)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return pasta


def _instalar_ligada(lg: Lugares, pasta: Path) -> None:
    resultado = instalador.instalar(str(pasta), lugares=lg)
    instalador.ligar(resultado.entrada.id, permissoes_vistas=resultado.manifesto.permissoes,
                     lugares=lg)


def _escolher(lg: Lugares, mod_id: str, **valores: Any) -> None:
    manifesto = instalador.manifesto_instalado(mod_id, lugares=lg)
    for opcao_id, valor in valores.items():
        opcoes.guardar(manifesto, opcao_id, valor, lg)


def _guardado(lg: Lugares, mod_id: str) -> dict[str, Any]:
    arquivo = opcoes.caminho(mod_id, lg)
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}


@pytest.fixture
def lg(tmp_path: Path) -> Lugares:
    return _lugares(tmp_path)


@pytest.fixture
def antiga_com_escolhas(lg: Lugares, tmp_path: Path) -> None:
    """A antiga instalada, ligada, com três escolhas feitas por quem usa."""
    _instalar_ligada(lg, _pasta(tmp_path, ANTIGA, opcoes_=OPCOES_DA_ANTIGA))
    _escolher(lg, ANTIGA, porta=21000, modo="b", so_na_antiga=True)


def _nova_que_ja_estava(lg: Lugares, tmp_path: Path, *, ligada: bool) -> None:
    """A nova instalada antes (1.0.0), sem ``substitui``, com o «sim» dado."""
    _instalar_ligada(lg, _pasta(tmp_path, NOVA, opcoes_=OPCOES_DA_NOVA))
    if not ligada:
        instalador.desligar(NOVA, lugares=lg)


def _publicar_a_nova(tmp_path: Path, **mais: Any) -> Path:
    mais.setdefault("opcoes_", OPCOES_DA_NOVA)
    return _pasta(tmp_path, NOVA, versao="2.0.0", substitui=(ANTIGA,), **mais)


# --- as escolhas -------------------------------------------------------------------------


def test_a_escolha_que_a_nova_aceita_passa_e_a_que_nao_aceita_fica_no_padrao(
        lg: Lugares, tmp_path: Path, antiga_com_escolhas: None) -> None:
    # D-2210-A-LOVENSE-E-UMA-EXTENSAO-SO.
    _nova_que_ja_estava(lg, tmp_path, ligada=False)
    instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg)
    nova = instalador.manifesto_instalado(NOVA, lugares=lg)
    valores = opcoes.ler(nova, lg)
    assert valores["porta"] == 21000, "a escolha de id igual e valor aceito passa"
    assert valores["modo"] == "a", "«b» não é escolha da nova: cai no padrão dela"
    assert valores["so_na_nova"] is True, "a opção que só a nova tem fica no padrão"
    assert "so_na_antiga" not in _guardado(lg, NOVA), "o id que a nova não tem não passa"
    assert "modo" not in _guardado(lg, NOVA), "o valor recusado nem entra no arquivo"


def test_a_escolha_que_ela_ja_fez_na_nova_vale_mais_que_a_da_antiga(
        lg: Lugares, tmp_path: Path, antiga_com_escolhas: None) -> None:
    _nova_que_ja_estava(lg, tmp_path, ligada=False)
    _escolher(lg, NOVA, porta=22000)
    instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg)
    nova = instalador.manifesto_instalado(NOVA, lugares=lg)
    assert opcoes.ler(nova, lg)["porta"] == 22000


def test_o_padrao_gravado_na_nova_nao_tapa_a_escolha_da_antiga(
        lg: Lugares, tmp_path: Path, antiga_com_escolhas: None) -> None:
    """O ``guardar`` grava o arquivo inteiro: escolher «modo» na nova grava também a «porta» no
    padrão, e esse padrão não é escolha de ninguém. A da antiga passa por cima dele."""
    _nova_que_ja_estava(lg, tmp_path, ligada=False)
    _escolher(lg, NOVA, modo="c")
    assert _guardado(lg, NOVA)["porta"] == 20010, "o guardar materializa o padrão"
    instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg)
    nova = instalador.manifesto_instalado(NOVA, lugares=lg)
    valores = opcoes.ler(nova, lg)
    assert valores["porta"] == 21000, "a escolha da antiga vence o padrão gravado"
    assert valores["modo"] == "c", "a escolha feita na nova continua valendo mais"


def test_a_instalacao_nova_sem_a_antiga_instalada_segue_sem_erro(lg: Lugares,
                                                                   tmp_path: Path) -> None:
    resultado = instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg)
    assert resultado.entrada.id == NOVA
    assert resultado.substituidas == []
    assert _guardado(lg, NOVA) == {}


# --- a antiga sai --------------------------------------------------------------------------


def test_a_antiga_sai_com_codigo_dados_e_registro(
        lg: Lugares, tmp_path: Path, antiga_com_escolhas: None) -> None:
    assert (lg.codigo / ANTIGA).is_dir() and (lg.dados / ANTIGA).is_dir()
    resultado = instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg)
    assert resultado.substituidas == [ANTIGA]
    assert not (lg.codigo / ANTIGA).exists()
    assert not (lg.dados / ANTIGA).exists()
    assert ANTIGA not in instalador.ler_registro(lg.registro)
    assert instalador.conferir_remocao(ANTIGA, lugares=lg) == []
    assert NOVA in instalador.ler_registro(lg.registro)


def test_a_antiga_que_nao_para_segura_a_troca_inteira(
        lg: Lugares, tmp_path: Path, antiga_com_escolhas: None,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Trocar com a antiga viva dividiria a porta com a nova: nada se troca, e a antiga segue."""
    original = instalador.esperar_parar
    monkeypatch.setattr(instalador, "esperar_parar",
                        lambda mod_id, **k: False if mod_id == ANTIGA else original(mod_id, **k))
    with pytest.raises(InstalacaoRecusadaError, match=f"«Extensão {ANTIGA}», .* não parou"):
        instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg)
    registro = instalador.ler_registro(lg.registro)
    assert registro[ANTIGA].ligada, "a antiga volta a seguir ligada"
    assert NOVA not in registro
    assert (lg.codigo / ANTIGA).is_dir()


# --- ligada, desligada e o «sim» -------------------------------------------------------------


def test_a_antiga_ligada_liga_a_nova_que_ja_tinha_o_sim(
        lg: Lugares, tmp_path: Path, antiga_com_escolhas: None) -> None:
    _nova_que_ja_estava(lg, tmp_path, ligada=False)
    resultado = instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg)
    assert resultado.entrada.ligada
    assert instalador.ler_registro(lg.registro)[NOVA].ligada


def test_a_antiga_desligada_nao_liga_a_nova(lg: Lugares, tmp_path: Path,
                                            antiga_com_escolhas: None) -> None:
    instalador.desligar(ANTIGA, lugares=lg)
    _nova_que_ja_estava(lg, tmp_path, ligada=False)
    instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg)
    assert not instalador.ler_registro(lg.registro)[NOVA].ligada


def test_a_antiga_desligada_nao_desliga_a_nova_que_ela_ja_usava(
        lg: Lugares, tmp_path: Path, antiga_com_escolhas: None) -> None:
    instalador.desligar(ANTIGA, lugares=lg)
    _nova_que_ja_estava(lg, tmp_path, ligada=True)
    instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg)
    assert instalador.ler_registro(lg.registro)[NOVA].ligada


def test_a_permissao_nova_continua_pedindo_o_sim(
        lg: Lugares, tmp_path: Path, antiga_com_escolhas: None) -> None:
    """Herdar as escolhas não herda o consentimento: a nova pede mais do que o «sim» dado."""
    _nova_que_ja_estava(lg, tmp_path, ligada=False)
    resultado = instalador.instalar(
        str(_publicar_a_nova(tmp_path, permissoes=("ler:estado", "ler:botoes"))), lugares=lg)
    nova = instalador.ler_registro(lg.registro)[NOVA]
    assert resultado.permissoes_novas == ["ler:botoes"]
    assert nova.permissoes_aceitas == ["ler:estado"], "as da antiga não se somam"
    assert not nova.ligada, "ligar a que pede permissão nova é do «sim» dela"
    nova_manifesto = instalador.manifesto_instalado(NOVA, lugares=lg)
    assert opcoes.ler(nova_manifesto, lg)["porta"] == 21000, "mas as escolhas passam"
    assert ANTIGA not in instalador.ler_registro(lg.registro)


def test_a_atualizacao_sozinha_nao_leva_embora_a_extensao_de_ninguem(
        lg: Lugares, tmp_path: Path, antiga_com_escolhas: None) -> None:
    """Tirar uma extensão do ar é gesto de quem usa: a sozinha espera o «Atualizar»."""
    _nova_que_ja_estava(lg, tmp_path, ligada=False)
    resultado = instalador.instalar(str(_publicar_a_nova(tmp_path)), lugares=lg, sozinha=True)
    assert resultado.trocou is False
    assert (lg.codigo / ANTIGA).is_dir()
    nova = instalador.ler_registro(lg.registro)[NOVA]
    assert nova.versao_esperando == "2.0.0"
    # a frase vai à dica do «Atualizar»: quem usa conhece a extensão pelo nome
    assert nova.motivo_da_espera == f"A versão 2.0.0 toma o lugar de «Extensão {ANTIGA}».", (
        nova.motivo_da_espera)


# --- a régua do manifesto ------------------------------------------------------------------


def _manifesto(**mais: Any) -> dict[str, Any]:
    base = {"id": NOVA, "nome": "Nova", "versao": "2.0.0", "api": ">=2,<3",  # (noqa-acento)
            "licenca": "MIT", "tipos": ["tema"], "permissoes": ["tema"]}  # (noqa-acento)
    return {**base, **mais}


def test_a_regua_aceita_uma_lista_de_ids() -> None:
    assert Manifesto.model_validate(_manifesto(substitui=[ANTIGA, "outra-velha"])).substitui == [
        ANTIGA, "outra-velha"]
    assert Manifesto.model_validate(_manifesto()).substitui == []


@pytest.mark.parametrize("substitui, motivo", [
    ([NOVA], "a si mesma"),
    (["Id Torto"], "fora da forma"),
    ([""], "fora da forma"),
    ([ANTIGA, ANTIGA], "repetido"),
    (["steam"], "vem com o Hefesto"),
    (["heroic"], "vem com o Hefesto"),
    (ANTIGA, "list"),
    ([3], "str"),
])
def test_a_regua_recusa_o_que_nao_e_substituir(substitui: Any, motivo: str) -> None:
    with pytest.raises(ValueError, match=motivo):
        Manifesto.model_validate(_manifesto(substitui=substitui))


def test_o_mecanismo_nao_cita_extensao_nenhuma() -> None:
    """O Hefesto não sabe qual extensão tomou o lugar de qual: o nome é do manifesto."""
    raiz = Path(instalador.__file__).parent
    for arquivo in ("instalador.py", "opcoes.py", "manifesto.py"):
        texto = (raiz / arquivo).read_text(encoding="utf-8").lower()
        for nome in ("intiface", "lovense", "buttplug"):
            assert nome not in texto, (arquivo, nome)
