-- Keep only Internet links clickable: links to local files, anchors and other schemes become plain text.
function Link(l)
  local t = l.target:lower()
  if t:find("^https?://") then return nil end
  return l.content
end
