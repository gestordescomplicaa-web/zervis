// Sem Kotlin: Java e as APIs do próprio Android, mais o OkHttp para o WebSocket (o OkHttp 5 traz
// um pouco de AndroidX por dentro; o app não usa).
// A versão vem da CI (VERSAO_CODIGO); a assinatura, da chave guardada nos segredos do repositório,
// para cada versão nova instalar por cima da anterior. O app procura a versão nova na versão
// "app-voz" do repositório que o compilou (GITHUB_REPOSITORY, na CI).
plugins {
    id("com.android.application")
}

val versao = (System.getenv("VERSAO_CODIGO") ?: "1").toInt()
val loja = System.getenv("ZE_VOZ_KEYSTORE")
val repositorio = System.getenv("GITHUB_REPOSITORY") ?: "gestordescomplicaa-web/zervis"

android {
    namespace = "com.zervis.voz"
    compileSdk = 37 // o OkHttp 5.5 pede; o comportamento segue o targetSdk

    defaultConfig {
        applicationId = "com.zervis.voz"
        minSdk = 30
        targetSdk = 36
        versionCode = versao
        versionName = "0.1.$versao"
        buildConfigField(
            "String",
            "VERSOES",
            "\"https://github.com/$repositorio/releases/download/app-voz/\"",
        )
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

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:5.5.1")
}
