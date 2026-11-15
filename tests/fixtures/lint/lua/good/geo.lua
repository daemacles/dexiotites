-- Sample module that follows COMMENTING.md: ground geometry helpers.

local M = {}

--- Returns the camera-to-ground distance along the optical axis.
---@param height_m number Camera height above the ground, in meters.
---@param pitch_rad number Downward pitch from horizontal, in radians.
---@return number range_m Slant range in meters.
function M.slant_range(height_m, pitch_rad)
  return height_m / math.sin(pitch_rad)
end

return M
