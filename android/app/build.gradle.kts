// Sem Kotlin e sem AndroidX: Java e as APIs do próprio Android, mais o OkHttp para o WebSocket.
// A versão vem da CI (VERSAO_CODIGO); a assinatura, da chave guardada nos segredos do repositório,
// para cada versão nova instalar por cima da anterior.
plugins {
    id("com.android.application")
}

val versao = (System.getenv("VERSAO_CODIGO") ?: "1").toInt()
val loja = System.getenv("ZE_VOZ_KEYSTORE")

android {
    namespace = "com.zervis.voz"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.zervis.voz"
        minSdk = 30
        targetSdk = 36
        versionCode = versao
        versionName = "0.1.$versao"
    }

    signingConfigs {
        if (loja != null) {
            create("ze") {
                storeFile = file(loja)
                storePassword = System.getenv("ZE_VOZ_SENHA")
                keyAlias = "ze-voz"
                keyPassword = System.getenv("ZE_VOZ_SENHA")
                storeType = "pkcs12"
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (loja != null) signingConfig = signingConfigs.getByName("ze")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:5.5.1")
}
