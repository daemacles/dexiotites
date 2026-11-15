/*
 * Sample file that follows COMMENTING.md.
 */
package sample

/**
 * A point on the ground.
 *
 * @property xMeters Eastward offset in meters.
 * @property yMeters Northward offset in meters.
 */
data class GroundPoint(val xMeters: Float, val yMeters: Float)

/**
 * Counts votes per sweep.
 *
 * @param window Number of recent sweeps that count toward votes.
 */
class Tracker(private val window: Int) {
    /** Votes recorded so far. */
    val votes: Int = 0

    /**
     * Returns true when a track has enough votes.
     *
     * @param hits Hits within the window.
     * @return Whether the track is confirmed.
     */
    fun confirmed(hits: Int): Boolean = hits * 2 >= window

    // Private helpers may carry comments; the standard asks for them.
    /** Clamps a hit count to the window size. */
    private fun clamp(hits: Int): Int = minOf(hits, window)
}
