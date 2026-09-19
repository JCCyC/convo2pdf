-- Inline code as a \texttt that may wrap after punctuation, so long paths and commands stay inside the margin.
local esc = {["\\"] = "\\textbackslash{}", ["{"] = "\\{", ["}"] = "\\}", ["$"] = "\\$", ["%"] = "\\%",
  ["&"] = "\\&", ["#"] = "\\#", ["_"] = "\\_", ["^"] = "\\textasciicircum{}", ["~"] = "\\textasciitilde{}",
  ["<"] = "\\textless{}", [">"] = "\\textgreater{}", ["|"] = "\\textbar{}", ['"'] = "\\textquotedbl{}",
  ["'"] = "\\textquotesingle{}", ["`"] = "\\textasciigrave{}", [" "] = "\\ "}
local breakable = "/-._=,:;)]"

function Code(c)
  local out = {}
  for ch in c.text:gmatch(utf8.charpattern) do
    out[#out + 1] = esc[ch] or ch
    if breakable:find(ch, 1, true) then out[#out + 1] = "\\allowbreak{}" end
  end
  return pandoc.RawInline("latex", "\\texttt{" .. table.concat(out) .. "}")
end
