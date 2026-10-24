plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// Le code Python et la page web sont ceux de la racine du dépôt : on les copie au build
val repoRoot: File = rootDir.parentFile
val generated = layout.buildDirectory.dir("generated/mpd")

// VERSION_NAME = tag git (v1.2.3) en CI
val appVersion = System.getenv("VERSION_NAME")?.removePrefix("v")
    ?.takeIf { it.matches(Regex("""\d+\.\d+\.\d+""")) } ?: "1.0.0"
val appVersionCode = appVersion.split(".").map { it.toInt() }.let { it[0] * 10000 + it[1] * 100 + it[2] }

android {
    namespace = "com.kudozu.playlistdownloader"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.kudozu.playlistdownloader"
        minSdk = 26
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersion
        // Python 3.12 n'existe qu'en 64 bits ; x86_64 sert à l'émulateur de la CI
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }

    signingConfigs {
        create("release") {
            System.getenv("KEYSTORE_FILE")?.let {
                storeFile = file(it)
                storePassword = System.getenv("KEYSTORE_PASSWORD")
                keyAlias = System.getenv("KEY_ALIAS")
                keyPassword = System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName(
                if (System.getenv("KEYSTORE_FILE") != null) "release" else "debug"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    sourceSets["main"].assets.srcDir(generated.map { it.dir("assets") })
}

chaquopy {
    defaultConfig {
        version = "3.12"
        pip {
            install("flask")
            install("waitress")
            install("yt-dlp")
            install("mutagen")
            install("qrcode")
            install("certifi")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("build/generated/mpd/python")
        }
    }
}

val copySharedCode by tasks.registering(Sync::class) {
    into(generated)
    from(repoRoot) {
        include("app.py", "ytdlp_update.py")
        into("python")
    }
    from(File(repoRoot, "static")) { into("assets/web") }
}

tasks.configureEach {
    if (name != copySharedCode.name && (name.contains("Python") || name.contains("Assets") || name == "preBuild")) {
        dependsOn(copySharedCode)
    }
}
