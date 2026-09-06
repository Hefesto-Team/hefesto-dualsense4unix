"""Gravar o perfil ATIVO manda o controle reaplicá-lo — mesmo com o daemon mudo.

Até 05/09/2026 `interface/pacotes/perfil.gravar_e_reaplicar` decidia assim::

    ativo_agora = str((getattr(ctx, "state", None) or {}).get("active_profile") or "")
    if ativo_agora and mesmo_slug(ativo_agora, era or prof.name):
        p.profile_switch(prof.name)

Lia o campo CRU. E o dono da pergunta
(`app/actions/profiles_actions.perfil_que_esta_valendo:574`) documenta, com
todas as letras, que o campo cru não serve:

    "Sobrevive ao daemon responder `active_profile: null`, que é o estado da
     máquina dela hoje"

Com `null`, `ativo_agora` ficava vazio, o `if` era falso, e o `profile.switch`
**nunca saía**. O `.json` mudava no disco e o controle continuava com o perfil
anterior — enquanto a MESMA aba realçava a linha, porque o realce
(`a10_perfis._valendo`) já usava o dono certo.

É o sintoma que ela leu como *"não está salvando"*, e a própria docstring da
função o anunciava duas linhas acima: *"Gravar sem reaplicar deixa a tela
dizendo uma coisa e o aparelho fazendo outra"*.

Esta régua LÊ o comportamento: monta o estado que a máquina dela publica hoje e
confere que o `profile.switch` sai.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import perfil as mod


class _Ponte:
    """O dublê da ponte de IPC. Guarda o que foi pedido, não finge saber."""

    def __init__(self) -> None:
        self.trocou: list[str] = []
        self.chamou: list[str] = []

    def profile_switch(self, nome: str) -> None:
        self.trocou.append(nome)

    def chamar(self, metodo: str, **_kw: Any) -> None:
        self.chamou.append(metodo)


@pytest.fixture
def gravado(monkeypatch):
    """Não escreve no disco dela: o `save_profile` vira um registrador."""
    escritos: list[Any] = []
    loader = SimpleNamespace(save_profile=lambda prof, **_kw: escritos.append(prof))
    monkeypatch.setattr(mod, "_com_o_src", lambda: loader)
    return escritos


def _mandar(estado, ponte, gravado, *, nome="Jogos", era=""):
    mod.gravar_e_reaplicar(SimpleNamespace(name=nome), SimpleNamespace(state=estado),
                           ponte, era=era)
    assert gravado, "o perfil não chegou ao disco"


def test_com_o_daemon_mudo_o_controle_ainda_reaplica(monkeypatch, gravado):
    """`active_profile: null` é o estado da máquina dela — e era o buraco."""
    monkeypatch.setattr(
        mod, "gravar_e_reaplicar", mod.gravar_e_reaplicar, raising=False
    )
    import hefesto_dualsense4unix.app.actions.profiles_actions as pa

    monkeypatch.setattr(
        pa, "perfil_que_esta_valendo",
        lambda _s=None: pa.PerfilQueVale("Jogos", "disco"),
    )
    ponte = _Ponte()
    _mandar({"active_profile": None}, ponte, gravado)
    assert ponte.trocou == ["Jogos"], (
        "o perfil foi gravado e o controle NÃO recebeu `profile.switch`. Se "
        "voltou a ler `active_profile` cru, com o daemon respondendo null o "
        "`if` é falso e o aparelho fica no perfil anterior."
    )


def test_o_perfil_que_nao_esta_valendo_nao_dispara_troca(monkeypatch, gravado):
    """Salvar um perfil qualquer não pode trocar o que está no controle."""
    import hefesto_dualsense4unix.app.actions.profiles_actions as pa

    monkeypatch.setattr(
        pa, "perfil_que_esta_valendo",
        lambda _s=None: pa.PerfilQueVale("Outro", "disco"),
    )
    ponte = _Ponte()
    _mandar({"active_profile": None}, ponte, gravado)
    assert ponte.trocou == [], "trocou o perfil do controle por um que não é o ativo"


def test_a_antecipacao_de_lancamento_sai_sempre(monkeypatch, gravado):
    import hefesto_dualsense4unix.app.actions.profiles_actions as pa

    monkeypatch.setattr(
        pa, "perfil_que_esta_valendo",
        lambda _s=None: pa.PerfilQueVale("Outro", "disco"),
    )
    ponte = _Ponte()
    _mandar({"active_profile": None}, ponte, gravado)
    assert "launch_env.refresh" in ponte.chamou


def test_o_renomear_casa_com_o_nome_anterior(monkeypatch, gravado):
    """Num renomear, o daemon ainda não ouviu falar do nome novo."""
    import hefesto_dualsense4unix.app.actions.profiles_actions as pa

    monkeypatch.setattr(
        pa, "perfil_que_esta_valendo",
        lambda _s=None: pa.PerfilQueVale("Antigo", "disco"),
    )
    ponte = _Ponte()
    _mandar({"active_profile": None}, ponte, gravado, nome="Novo", era="Antigo")
    assert ponte.trocou == ["Novo"]


def test_o_dono_tem_a_perna_de_disco_que_o_campo_cru_nao_tem():
    """A MORDIDA, sem tocar no código: prova que o defeito era real.

    Aqui o lar é de mentira (o `conftest.py` desvia `HOME` e os quatro `XDG_*`),
    então não há marcador em disco e o dono responde `nao_sei`. Na máquina dela
    há: medido em 05/09/2026, com `active_profile: null` o dono responde
    `PerfilQueVale(nome='Personalizado', fonte='disco')` e o campo cru responde
    `''`. O que esta régua prova é o MECANISMO — que o dono tem uma segunda
    perna e o campo cru não tem nenhuma.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        perfil_que_esta_valendo,
    )

    # Com o daemon falando, as duas fontes concordam.
    assert perfil_que_esta_valendo({"active_profile": "Jogos"}).nome == "Jogos"

    # Com o daemon mudo, o campo cru não tem para onde ir...
    estado = {"active_profile": None}
    assert str(estado.get("active_profile") or "") == ""

    # ...e o dono vai ao disco, em vez de devolver vazio por omissão.
    vale = perfil_que_esta_valendo(estado)
    assert vale.fonte != "daemon", (
        "o dono devolveu 'daemon' sobre uma resposta nula: a perna de disco "
        "sumiu, e com ela a cura deste arquivo"
    )
