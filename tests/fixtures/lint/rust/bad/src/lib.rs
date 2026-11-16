pub fn parse_meters(text: &str) -> Result<f64, std::num::ParseFloatError> {
    text.parse()
}

/// Has docs but no `# Errors` section, and a broken link to [Missing].
pub fn parse_again(text: &str) -> Result<f64, std::num::ParseFloatError> {
    text.parse()
}

/// Reads a value.
pub unsafe fn read(ptr: *const u32) -> u32 {
    unsafe { *ptr }
}

/// Returns the first byte of `bytes`.
pub fn first(bytes: &[u8]) -> u8 {
    *bytes.first().unwrap()
}
