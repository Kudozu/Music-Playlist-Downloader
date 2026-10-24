package com.kudozu.playlistdownloader

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.Process
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import kotlin.concurrent.thread

/**
 * Fait tourner le serveur Python au premier plan, pour que les téléchargements
 * continuent quand l'appli est en arrière-plan ou l'écran éteint.
 */
class ServerService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "Téléchargements", NotificationManager.IMPORTANCE_LOW)
        )
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE
        )
        val quit = PendingIntent.getService(
            this, 1, Intent(this, ServerService::class.java).setAction(ACTION_QUIT), PendingIntent.FLAG_IMMUTABLE
        )
        val notification = Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat)
            .setContentTitle("Playlist Downloader")
            .setContentText("Prêt à télécharger")
            .setContentIntent(open)
            .addAction(Notification.Action.Builder(null, "Quitter", quit).build())
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(1, notification)
        }
        startPython()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_QUIT) {
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            Process.killProcess(Process.myPid())
        }
        return START_STICKY
    }

    private fun startPython() {
        if (started) return
        started = true
        thread(name = "python-server") {
            val static = copyWebAssets()
            if (!Python.isStarted()) Python.start(AndroidPlatform(this))
            Python.getInstance().getModule("android_main")
                .callAttr("start", filesDir.absolutePath, static.absolutePath)
        }
    }

    /** La page web est dans les assets de l'APK ; Flask a besoin de vrais fichiers. */
    private fun copyWebAssets(): File {
        val out = File(filesDir, "static").apply { deleteRecursively(); mkdirs() }
        assets.list("web")?.forEach { name ->
            assets.open("web/$name").use { input -> File(out, name).outputStream().use { input.copyTo(it) } }
        }
        return out
    }

    companion object {
        private const val CHANNEL = "server"
        private const val ACTION_QUIT = "quit"
        @Volatile private var started = false
    }
}
