//! Sample crate that follows COMMENTING.md.

/// Parses a distance in meters from text.
///
/// # Errors
///
/// Returns an error if `text` is not a decimal number.
pub fn parse_meters(text: &str) -> Result<f64, std::num::ParseFloatError> {
    text.parse()
}

/// Returns the first byte of `bytes`.
///
/// # Panics
///
/// Panics if `bytes` is empty.
pub fn first(bytes: &[u8]) -> u8 {
    bytes[0]
}

/// Reads the value behind `ptr`.
///
/// # Safety
///
/// `ptr` must be non-null, aligned, and point to an initialized `u32`.
pub unsafe fn read(ptr: *const u32) -> u32 {
    // SAFETY: the caller upholds this function's `# Safety` contract.
    unsafe { *ptr }
}
