package com.aras.client.ui.main

import androidx.compose.animation.animateColorAsState
import android.app.Activity
import android.graphics.RectF
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.ColorMatrix
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.graphics.painter.BitmapPainter
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.PlatformTextStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import com.caverock.androidsvg.SVG
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.aras.client.AppConfig
import com.aras.client.R
import com.aras.client.ui.compose.FlagIcon
import com.aras.client.ui.compose.formatDuration
import com.aras.client.util.ConnectionStatsManager
import kotlinx.coroutines.delay
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    mainViewModel: MainViewModel,
    onAction: (MainAction) -> Unit,
    onNavigate: (MainDestination) -> Unit,
) {
    if (!AppConfig.SINGLE_PROFILE_MODE) {
        LegacyMainScreen(mainViewModel, onAction, onNavigate)
        return
    }
    val state by mainViewModel.uiState.collectAsStateWithLifecycle()
    var showImport by remember { mutableStateOf(false) }
    LifecycleResumeEffect(mainViewModel) {
        mainViewModel.setMainScreenActive(true)
        onPauseOrDispose { mainViewModel.setMainScreenActive(false) }
    }
    val testing = state.isTesting || state.status == MainStatus.Testing
    val ready = !state.selectedGuid.isNullOrBlank()
    val active = state.isRunning && !state.isConnecting
    val accent by animateColorAsState(
        if (active) Color(0xFF35D88A) else if (state.isConnecting) Color(0xFFF4BE63) else Color(0xFFE74E62),
        label = "connectionColor",
    )
    val powerDescription = stringResource(
        if (state.isRunning || state.isConnecting) R.string.tesla_disconnect else R.string.tesla_connect)
    val status = when {
        state.isConnecting -> stringResource(R.string.connection_connecting)
        active -> stringResource(R.string.tesla_connected)
        else -> stringResource(R.string.tesla_disconnected)
    }
    val view = LocalView.current
    SideEffect {
        (view.context as? Activity)?.window?.let { window ->
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = false
                isAppearanceLightNavigationBars = false
            }
        }
    }
    TeslaConnectionContent(
        ready = ready,
        active = active,
        connecting = state.isConnecting,
        running = state.isRunning,
        testing = testing,
        accent = accent,
        status = status,
        powerDescription = powerDescription,
        countryCode = state.exitCountryCode,
        detail = if (state.statusMessageVisible &&
            (state.status is MainStatus.ConnectionTest || state.status is MainStatus.TestProgress)) {
            mainViewModel.formatStatus(state.status)
        } else "",
        onToggle = { onAction(MainAction.ToggleService) },
        onTest = { onAction(MainAction.TestCurrentServer) },
        onImport = { showImport = true },
    )
    if (showImport) {
        ModalBottomSheet(
            onDismissRequest = { showImport = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = Color(0xFF141F33),
            contentColor = Color.White,
            shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
        ) {
            Column(
                Modifier.fillMaxWidth().heightIn(max = 520.dp)
                    .verticalScroll(rememberScrollState())
                    .padding(start = 24.dp, end = 24.dp, bottom = 24.dp),
            ) {
                Text(stringResource(R.string.tesla_import_config),
                    style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(16.dp))
                listOf(
                    R.string.menu_item_import_config_qrcode to MainAction.ImportQRcode,
                    R.string.menu_item_import_config_clipboard to MainAction.ImportClipboard,
                    R.string.menu_item_import_config_local to MainAction.ImportConfigLocal,
                ).forEach { (label, action) ->
                    TextButton(
                        onClick = { showImport = false; onAction(action) },
                        modifier = Modifier.fillMaxWidth().heightIn(min = 60.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.textButtonColors(contentColor = Color.White),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 16.dp),
                    ) {
                        Icon(painterResource(R.drawable.ic_add_24dp), contentDescription = null,
                            modifier = Modifier.size(24.dp), tint = Color(0xFFE74E62))
                        Spacer(Modifier.width(16.dp))
                        Text(stringResource(label), modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.bodyLarge)
                    }
                }
            }
        }
    }
}

private val TeslaBackground = Color(0xFF0F1626)
private val TeslaSecondary = Color(0xFF98ABD5)
private val TeslaFont = FontFamily(
    Font(R.font.geologica_light, FontWeight.Light),
    Font(R.font.geologica_regular, FontWeight.Normal),
    Font(R.font.geologica_medium, FontWeight.Medium),
    Font(R.font.geologica_bold, FontWeight.Bold),
)

/** Render the original local SVG with its intrinsic size and gradient intact. */
@Composable
private fun figmaPainter(asset: String): Painter {
    val context = LocalContext.current
    val original = remember(asset, context) {
        context.assets.open("figma/$asset").bufferedReader().use { it.readText() }
    }
    return remember(original) {
        val svg = SVG.getFromString(original)
        val picture = svg.renderToPicture()
        object : Painter() {
            override val intrinsicSize = Size(svg.documentWidth, svg.documentHeight)
            override fun DrawScope.onDraw() {
                drawIntoCanvas { canvas ->
                    canvas.nativeCanvas.drawPicture(picture, RectF(0f, 0f, size.width, size.height))
                }
            }
        }
    }
}

/** Use Figma's exported layer to avoid Android SVG shader interpolation differences.
 * The matrix maps the original red to the animated accent, keeping the dark
 * background, alpha, and the exported gradient's falloff intact. */
@Composable
private fun connectionGlow(accent: Color): Pair<Painter, ColorFilter> {
    val context = LocalContext.current
    val painter = remember(context) {
        val bitmap = context.assets.open("figma/connection-glow.png").use { BitmapFactory.decodeStream(it) }
        BitmapPainter(bitmap.asImageBitmap())
    }
    val filter = remember(accent) {
        val red = (accent.red * 255 - 231) / 216
        val green = (accent.green * 255 - 78) / 216
        val blue = (accent.blue * 255 - 98) / 216
        ColorFilter.colorMatrix(ColorMatrix(floatArrayOf(
            1 + red, 0f, 0f, 0f, -15 * red,
            green, 1f, 0f, 0f, -15 * green,
            blue, 0f, 1f, 0f, -15 * blue,
            0f, 0f, 0f, 1f, 0f,
        )))
    }
    return painter to filter
}

/** Figma 15:183, 451 × 852. Uniform scaling keeps the design on smaller phones
 * and landscape/TV displays without clipping any controls or system insets. */
@Composable
private fun TeslaConnectionContent(
    ready: Boolean,
    active: Boolean,
    connecting: Boolean,
    running: Boolean,
    testing: Boolean,
    accent: Color,
    status: String,
    powerDescription: String,
    detail: String,
    countryCode: String?,
    onToggle: () -> Unit,
    onTest: () -> Unit,
    onImport: () -> Unit,
) {
    var sessionMillis by remember { mutableLongStateOf(0L) }
    LaunchedEffect(active) {
        if (!active) sessionMillis = 0L
        while (active) {
            sessionMillis = ConnectionStatsManager.sessionElapsedMillis()
            delay(1000)
        }
    }
    BoxWithConstraints(
        Modifier.fillMaxSize().background(TeslaBackground).safeDrawingPadding(),
        contentAlignment = Alignment.Center,
    ) {
        val scale = minOf(maxWidth.value / 451f, maxHeight.value / 852f)
        val textStyle = TextStyle(
            fontFamily = TeslaFont,
            platformStyle = PlatformTextStyle(includeFontPadding = false),
            textAlign = TextAlign.Center,
        )
        Box(Modifier.size((451 * scale).dp, (852 * scale).dp)) {
            if (ready) {
                val (glowPainter, glowFilter) = connectionGlow(accent)
                Image(
                    painter = glowPainter, colorFilter = glowFilter,
                    contentDescription = null,
                    modifier = Modifier.offset((2 * scale).dp, (203 * scale).dp).size((446 * scale).dp),
                )
            }
            Column(
                Modifier.offset((79 * scale).dp, (92.5f * scale).dp).width((292 * scale).dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy((4 * scale).dp),
            ) {
                Text(
                    stringResource(R.string.app_name), color = Color.White,
                    modifier = Modifier.fillMaxWidth().height((51 * scale).dp).wrapContentHeight(),
                    style = textStyle, fontSize = (40 * scale).sp,
                    lineHeight = (51 * scale).sp, fontWeight = FontWeight.Bold,
                )
                Text(
                    stringResource(if (ready) R.string.tesla_tap_to_connect else R.string.tesla_import_hint),
                    color = Color(0xFFA5A5A5), style = textStyle, fontSize = (20 * scale).sp,
                    lineHeight = (25 * scale).sp,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            if (ready) {
                Box(
                    Modifier.offset((109.5f * scale).dp, (316.5f * scale).dp)
                        .size((231 * scale).dp).clip(CircleShape).background(accent)
                        .clickable(role = Role.Button, onClick = onToggle)
                        .semantics { contentDescription = powerDescription },
                ) {
                    Box(Modifier.offset((7.4298f * scale).dp, (8.1053f * scale).dp)
                        .size((216.1404f * scale).dp).border((1.3509f * scale).dp, TeslaBackground, CircleShape))
                    Image(
                        painter = figmaPainter("tesla-symbol.svg"), contentDescription = null,
                        modifier = Modifier.offset((40.8766f * scale).dp, (85.1103f * scale).dp)
                            .size((150.0813f * scale).dp, (99.5438f * scale).dp),
                    )
                    if (connecting) CircularProgressIndicator(
                        modifier = Modifier.fillMaxSize().padding((13.5088f * scale).dp),
                        color = TeslaBackground, strokeWidth = (2.7018f * scale).dp,
                    )
                }
                Text(
                    status, color = accent, style = textStyle,
                    fontSize = (20 * scale).sp, fontWeight = FontWeight.Medium,
                    modifier = Modifier.offset((118.5f * scale).dp, (564.5f * scale).dp)
                        .size((213 * scale).dp, (25 * scale).dp).wrapContentHeight(),
                    lineHeight = (25 * scale).sp,
                )
                if (active) {
                    Text(
                        formatDuration(sessionMillis), color = TeslaSecondary, style = textStyle,
                        fontSize = (20 * scale).sp, lineHeight = (25 * scale).sp,
                        modifier = Modifier.offset((65 * scale).dp, (601 * scale).dp)
                            .size((321 * scale).dp, (25 * scale).dp).wrapContentHeight(),
                    )
                    Row(
                        Modifier.offset((45 * scale).dp, (635 * scale).dp)
                            .size((361 * scale).dp, (25 * scale).dp),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        FlagIcon(countryCode, width = (24 * scale).dp, height = (18 * scale).dp)
                        if (countryCode != null) Spacer(Modifier.width((8 * scale).dp))
                        Text(
                            countryCode?.let { Locale("", it).getDisplayCountry(Locale.ENGLISH) }
                                ?: "Unknown country",
                            color = TeslaSecondary, style = textStyle, fontSize = (17 * scale).sp,
                            maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                        )
                    }
                }
                if (active) Box(
                    Modifier.offset((127.5f * scale).dp, (681 * scale).dp)
                        .size((195 * scale).dp, (37 * scale).dp)
                        .clip(CircleShape).border((1 * scale).dp, TeslaSecondary, CircleShape)
                        .clickable(enabled = active && !testing, role = Role.Button, onClick = onTest),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        stringResource(if (testing) R.string.connection_test_testing else R.string.connection_test_pending),
                        color = TeslaSecondary, style = textStyle,
                        fontSize = (18 * scale).sp, fontWeight = FontWeight.Light,
                        lineHeight = (23 * scale).sp,
                    )
                }
                if (detail.isNotBlank()) Text(
                    detail, color = Color(0xFFA5A5A5), style = textStyle,
                    fontSize = (16 * scale).sp, lineHeight = (22 * scale).sp,
                    modifier = Modifier.offset((45 * scale).dp, (733 * scale).dp)
                        .size((361 * scale).dp, (38 * scale).dp).verticalScroll(rememberScrollState()),
                )
            }
            if (!active) Box(
                Modifier.offset((110 * scale).dp, ((if (ready) 779 else 408) * scale).dp)
                    .size((238 * scale).dp, (37 * scale).dp)
                    .clip(CircleShape).background(Color(0xFF19253A))
                    .clickable(enabled = !running && !connecting, role = Role.Button, onClick = onImport),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    stringResource(if (ready) R.string.tesla_replace_config else R.string.tesla_import_config),
                    color = TeslaSecondary, style = textStyle,
                    fontSize = (20 * scale).sp, fontWeight = FontWeight.Light,
                    lineHeight = (25 * scale).sp,
                )
            }
        }
    }
}
