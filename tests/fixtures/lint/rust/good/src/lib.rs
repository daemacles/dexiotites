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

/// Returns twice `n`.
///
/// The explicit `return` is a deliberate clippy style finding (`needless_return`): the
/// documentation gate must report it without failing on it.
pub fn double(n: u32) -> u32 {
    return n * 2;
}
