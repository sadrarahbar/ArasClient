package com.aras.client.handler

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SingleProfilePolicyTest {
    @Test fun migrationPreservesCurrentProfileEvenWhenItIsNotFirst() {
        assertEquals("active", SingleProfilePolicy.choose(listOf("old", "active", "other"), "active"))
    }
    @Test fun migrationFallsBackWhenSelectionNoLongerExists() {
        assertEquals("valid", SingleProfilePolicy.choose(listOf("valid", "other"), "deleted"))
    }
    @Test fun batchChoosesFirstProfileWithoutInheritingOldSelection() {
        assertEquals("new-first", SingleProfilePolicy.choose(listOf("new-first", "new-second"), "old"))
    }
    @Test fun emptyStorageDoesNotInventASelection() {
        assertNull(SingleProfilePolicy.choose(emptyList(), "deleted"))
    }
}
