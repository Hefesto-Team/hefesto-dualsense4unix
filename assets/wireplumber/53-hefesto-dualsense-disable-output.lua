-- Hefesto - DualSense4Unix — FEAT-WIREPLUMBER-DISABLE-OUTPUT
--
-- DESABILITA (node.disabled) a SAÍDA do controle. Sem ela o monitor do sink não
-- reaparece como fonte padrão depois do boot; o alto-falante e o fone do
-- controle ficam mudos (a vibração dos jogos vai por HID e continua).
--
-- WirePlumber 0.4 (Ubuntu 24.04, Linux Mint 22, Debian 12): a mesma regra do
-- 53-…-disable-output.conf, na forma que o 0.4 lê (Lua em ~/.config/wireplumber/main.lua.d/). O
-- 0.4 IGNORA wireplumber.conf.d/ sem erro nenhum, por isso a regra SPA-JSON não
-- valia ali. O instalador escolhe a forma pela pasta de sistema do WirePlumber
-- (utils/xdg_paths.wireplumber_forma); no 0.5 este arquivo não é instalado.
--
-- O 0.4 casa por glob (`*` e `?`), não por regex: o `[Dd]ual[Ss]ense` da regra
-- SPA-JSON vira as quatro grafias abaixo.
--
-- Portão: tests/unit/test_as_regras_do_som_valem_no_wireplumber_da_distro.py

local grafias = { "DualSense", "Dualsense", "dualSense", "dualsense" }

local function casar(campo, prefixo, sufixo)
  local grupos = {}
  for _, g in ipairs(grafias) do
    table.insert(grupos, { { campo, "matches", prefixo .. g .. sufixo } })
  end
  return grupos
end

local saida = {
  matches = {},
  apply_properties = {
    ["node.disabled"] = true,
  },
}
for _, g in ipairs(casar("node.name", "alsa_output.*", "*")) do
  table.insert(saida.matches, g)
end
table.insert(alsa_monitor.rules, saida)
