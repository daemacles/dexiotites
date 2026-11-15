local M = {}

function M.slant_range(height_m, pitch_rad)
  return height_m / math.sin(pitch_rad)
end

--- Partly documented: the second parameter and the return value are missing.
---@param a number First value.
function M.add(a, b)
  return a + b
end

function GlobalHelper(x)
  return x
end

return M
