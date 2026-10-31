package com.aras.client.handler

import android.content.Context
import android.util.Base64
import com.aras.client.core.CoreConfigContextBuilder
import com.aras.client.core.aether.AetherCoreManager
import com.aras.client.core.aether.AetherIdentityManager
import com.aras.client.dto.entities.ProfileItem
import com.aras.client.enums.AetherProtocol
import com.aras.client.enums.AetherPsiphon
import com.aras.client.enums.AetherTor
import com.aras.client.enums.EConfigType
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.io.File

/** Nekoray 4 custom-external-core format; never exports the Android loopback hop. */
object NekorayAetherExporter {
    const val CORE_NAME = "aras-aether"
    sealed interface Result {
        data class Ready(val link: String) : Result
        data object Protected : Result
        data object Unsupported : Result
        data object MissingIdentity : Result
    }

    fun export(context: Context, guid: String): Result {
        if (ArasExportImportManager.isProtected(guid)) return Result.Protected
        val profile = MmkvManager.decodeServerConfig(guid) ?: return Result.Unsupported
        if (!supports(profile) || CoreConfigContextBuilder.resolveChainProfiles(context, guid).size != 1) {
            return Result.Unsupported
        }
        val protocol = AetherProtocol.fromString(profile.aetherProtocol)
        val work = AetherIdentityManager.workDir(context)
        val identityFile = if (protocol == AetherProtocol.MASQUE) {
            File(work, AetherIdentityManager.MASQUE_FILE)
        } else {
            File(work, AetherIdentityManager.WIREGUARD_FILE).takeIf { it.isFile }
                ?: File(work, AetherIdentityManager.BASE_FILE)
        }
        // Identity contents and share links must never enter application logs.
        val identity = runCatching { identityFile.readText() }.getOrNull()
            ?.takeIf { it.isNotBlank() } ?: return Result.MissingIdentity
        val bean = buildBean(profile, identity, AetherCoreManager.buildArguments(profile, 1080))
        val encoded = Base64.encodeToString(
            bean.toString().toByteArray(Charsets.UTF_8), Base64.URL_SAFE or Base64.NO_WRAP
        )
        return Result.Ready("nekoray://custom#$encoded")
    }

    internal fun supports(profile: ProfileItem): Boolean =
        profile.configType == EConfigType.AETHER &&
            (profile.aetherProtocol.isNullOrBlank() || profile.aetherProtocol in setOf("wg", "masque")) &&
            AetherProtocol.fromString(profile.aetherProtocol) in
                setOf(AetherProtocol.MASQUE, AetherProtocol.WIREGUARD) &&
            AetherPsiphon.fromString(profile.aetherPsiphon) != AetherPsiphon.ONLY &&
            AetherTor.fromString(profile.aetherTor) == AetherTor.OFF &&
            profile.aetherExitNode.isNullOrBlank() && profile.aetherCommand.isNullOrBlank()

    internal fun buildBean(profile: ProfileItem, identity: String, arguments: List<String>): JsonObject {
        require(supports(profile))
        require(identity.isNotBlank())
        val args = arguments.toMutableList()
        val bind = args.indexOf("--bind")
        require(bind >= 0 && bind + 1 < args.size)
        // Nekoray allocates this port per session. A fixed Android port is not portable.
        val psiphonInside = AetherPsiphon.fromString(profile.aetherPsiphon) == AetherPsiphon.CHAIN
        args[bind + 1] = if (psiphonInside) "127.0.0.1:%aether_port%" else "127.0.0.1:%socks_port%"
        if (psiphonInside) {
            val psiphonBind = args.indexOf("--psiphon-bind")
            require(psiphonBind >= 0 && psiphonBind + 1 < args.size)
            args[psiphonBind + 1] = "127.0.0.1:%socks_port%"
        }
        val payload = JsonObject().apply {
            addProperty("version", 1)
            addProperty("protocol", AetherProtocol.fromString(profile.aetherProtocol).type)
            addProperty("identity", identity)
            add("arguments", JsonArray().apply { args.forEach { add(it) } })
        }
        return JsonObject().apply {
            addProperty("_v", 0)
            addProperty("name", profile.remarks.ifBlank { "Aras Aether" })
            addProperty("addr", profile.server?.takeIf { it.isNotBlank() } ?: "127.0.0.1")
            addProperty("port", profile.serverPort?.toIntOrNull() ?: 443)
            addProperty("core", CORE_NAME)
            add("cmd", JsonArray().apply { add("%config%") })
            addProperty("cs", payload.toString())
            addProperty("cs_suffix", "json")
            addProperty("mapping_port", 0)
            addProperty("socks_port", 0)
        }
    }
}
