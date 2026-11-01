package com.aras.client.handler

/** Stable selection for migration and batch imports: preserve selection, otherwise take the first. */
internal object SingleProfilePolicy {
    fun choose(available: List<String>, selected: String?): String? =
        selected?.takeIf { it in available } ?: available.firstOrNull()
}
