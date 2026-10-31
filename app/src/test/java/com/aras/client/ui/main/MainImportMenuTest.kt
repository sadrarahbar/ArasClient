package com.aras.client.ui.main

import org.junit.Assert.assertEquals
import org.junit.Test

class MainImportMenuTest {

    @Test
    fun regularShareMenuContainsOnlyShareActions() {
        val expected = listOf(
            ServerMenuAction.ShareQRCode,
            ServerMenuAction.ShareClipboard,
            ServerMenuAction.ShareFullContent,
            ServerMenuAction.ShareTxtFile,
            ServerMenuAction.ShareArasc,
        )
        assertEquals(expected, serverMenuActions(isComplexProfile = false, includeManagementActions = false))
    }

    @Test
    fun regularMoreMenuContainsEveryActionInDisplayOrder() {
        assertEquals(
            ServerMenuAction.entries.filter { it != ServerMenuAction.ShareToV2Ray },
            serverMenuActions(isComplexProfile = false, includeManagementActions = true),
        )
    }

    @Test
    fun complexShareMenuContainsOnlyFullContent() {
        assertEquals(
            listOf(ServerMenuAction.ShareFullContent),
            serverMenuActions(isComplexProfile = true, includeManagementActions = false),
        )
    }

    @Test
    fun complexMoreMenuRetainsManagementActions() {
        val expected = listOf(
            ServerMenuAction.ShareFullContent,
            ServerMenuAction.Edit,
            ServerMenuAction.Delete,
        )
        assertEquals(expected, serverMenuActions(isComplexProfile = true, includeManagementActions = true))
    }

    @Test
    fun aetherOffersNekorayExportButProtectedProfilesDoNot() {
        assertEquals(true, ServerMenuAction.ShareToV2Ray in serverMenuActions(false, false, isAether = true))
        assertEquals(false, ServerMenuAction.ShareToV2Ray in serverMenuActions(false, false, isProtected = true, isAether = true))
    }

}
