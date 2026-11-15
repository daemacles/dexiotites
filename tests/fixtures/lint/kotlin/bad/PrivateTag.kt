package sample

/**
 * Private constructor value documented with the wrong tag.
 *
 * @property secret Should be @param because it is private.
 */
class Holder(private val secret: Int)
