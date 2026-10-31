package com.aras.client.handler

import com.aras.client.dto.entities.ProfileItem
import com.aras.client.enums.EConfigType
import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test

class NekorayAetherExporterTest {
    @Test
    fun portableProfileCarriesIdentityAndDynamicListenerInsteadOfAndroidLoopback() {
        val profile = ProfileItem.create(EConfigType.AETHER).apply {
            remarks = "تست"
            aetherProtocol = "masque"
        }
        val identity = "device_id = \"fixture\"\nkey_pem = \"fixture-key\""
        val bean = NekorayAetherExporter.buildBean(profile, identity,
            listOf("--bind", "127.0.0.1:1080", "--protocol", "masque", "--h2", "--fragment"))
        assertEquals("aras-aether", bean["core"].asString)
        assertEquals("%config%", bean["cmd"].asJsonArray[0].asString)
        assertEquals("تست", bean["name"].asString)
        val payload = JsonParser.parseString(bean["cs"].asString).asJsonObject
        assertEquals(identity, payload["identity"].asString)
        val args = payload["arguments"].asJsonArray.map { it.asString }
        assertEquals("127.0.0.1:%socks_port%", args[1])
        assertTrue("--h2" in args && "--fragment" in args)
        assertFalse(bean.toString().contains("127.0.0.1:1080"))
    }

    @Test
    fun dependentAndRawCommandProfilesAreRejectedInsteadOfSilentlyChangingTunnel() {
        val profile = ProfileItem.create(EConfigType.AETHER)
        assertTrue(NekorayAetherExporter.supports(profile))
        profile.aetherProtocol = "gool"
        assertFalse(NekorayAetherExporter.supports(profile))
        profile.aetherProtocol = "masque"
        profile.aetherTor = "chain"
        assertFalse(NekorayAetherExporter.supports(profile))
        profile.aetherTor = null
        profile.aetherExitNode = "another-profile"
        assertFalse(NekorayAetherExporter.supports(profile))
        profile.aetherExitNode = null
        profile.aetherCommand = "--protocol wg"
        assertFalse(NekorayAetherExporter.supports(profile))
    }

    @Test
    fun psiphonInsideWarpKeepsCountryAndGivesNekorayTheFinalListener() {
        val profile = ProfileItem.create(EConfigType.AETHER).apply {
            aetherProtocol = "masque"
            aetherPsiphon = "chain"
        }
        val bean = NekorayAetherExporter.buildBean(profile, "fixture",
            listOf("--bind", "127.0.0.1:1081", "--protocol", "masque", "--psiphon",
                "--psiphon-bind", "127.0.0.1:1080", "--psiphon-region", "DE"))
        val payload = JsonParser.parseString(bean["cs"].asString).asJsonObject
        val args = payload["arguments"].asJsonArray.map { it.asString }
        assertEquals("127.0.0.1:%aether_port%", args[1])
        assertEquals("127.0.0.1:%socks_port%", args[args.indexOf("--psiphon-bind") + 1])
        assertEquals("DE", args[args.indexOf("--psiphon-region") + 1])
    }
}
