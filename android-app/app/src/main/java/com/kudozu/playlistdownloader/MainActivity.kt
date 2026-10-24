package com.kudozu.playlistdownloader

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import kotlin.concurrent.thread

/** Affiche l'interface web servie par le serveur Python local (ServerService). */
class MainActivity : Activity() {

    private lateinit var web: WebView
    private var storageDialog: AlertDialog? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = BG
        window.navigationBarColor = BG

        web = WebView(this).apply {
            setBackgroundColor(BG)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webChromeClient = WebChromeClient() // alert() / confirm()
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    if (request.url.host == "127.0.0.1") return false
                    startActivity(Intent(Intent.ACTION_VIEW, request.url)) // liens externes : navigateur
                    return true
                }
            }
            loadDataWithBaseURL(null, LOADING, "text/html", "utf-8", null)
        }
        setContentView(web)

        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2)
        }
        startForegroundService(Intent(this, ServerService::class.java))
        openWhenReady(sharedUrl(intent))
    }

    override fun onResume() {
        super.onResume()
        if (!hasStorage() && storageDialog?.isShowing != true) askStorage()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        sharedUrl(intent)?.let { openWhenReady(it) }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else moveTaskToBack(true) // le serveur continue
    }

    /** Lien envoyé via « Partager » depuis YouTube Music. */
    private fun sharedUrl(intent: Intent?): String? {
        if (intent?.action != Intent.ACTION_SEND) return null
        val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return null
        return Regex("""https?://\S+""").find(text)?.value
    }

    private fun openWhenReady(shared: String?) {
        val page = BASE + "/" + (shared?.let { "?url=" + URLEncoder.encode(it, "UTF-8") } ?: "")
        thread {
            repeat(240) { // le premier lancement décompresse Python : jusqu'à ~1 min
                try {
                    val c = URL("$BASE/api/settings").openConnection() as HttpURLConnection
                    c.connectTimeout = 500
                    c.readTimeout = 2000
                    val ok = c.responseCode == 200
                    c.disconnect()
                    if (ok) {
                        runOnUiThread { web.loadUrl(page) }
                        return@thread
                    }
                } catch (_: Exception) {
                }
                Thread.sleep(250)
            }
        }
    }

    private fun hasStorage(): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) Environment.isExternalStorageManager()
        else checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED

    private fun askStorage() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            requestPermissions(arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE), 1)
            return
        }
        storageDialog = AlertDialog.Builder(this)
            .setTitle("Accès aux fichiers")
            .setMessage(
                "Pour enregistrer les musiques dans le dossier de ton choix (Music par défaut), " +
                    "active « Autoriser l'accès à tous les fichiers » sur l'écran suivant."
            )
            .setCancelable(false)
            .setPositiveButton("Continuer") { _, _ ->
                try {
                    startActivity(
                        Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION, Uri.parse("package:$packageName"))
                    )
                } catch (_: Exception) {
                    startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
                }
            }
            .show()
    }

    companion object {
        private const val BASE = "http://127.0.0.1:8765"
        private val BG = Color.parseColor("#121212")
        private const val LOADING = """
            <body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
              background:#121212;color:#9a9a9a;font:15px system-ui,sans-serif">Démarrage…</body>"""
    }
}
