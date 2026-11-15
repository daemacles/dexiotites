package sample

data class Undocumented(val a: Int)

/**
 * Wrong tags.
 *
 * @param a Should be @property because it is public.
 */
data class WrongTag(val a: Int)

/**
 * Stale docs.
 *
 * @param old No longer a parameter.
 */
fun stale(new: Int): Int = new

fun undocumented(x: Int): Int = x
