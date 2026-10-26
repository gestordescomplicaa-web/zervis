package com.zervis.voz;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * A atualização do próprio app: a CI publica, junto do ze-voz.apk, um versao.json com o número da
 * versão ({"codigo": N}). Procurar compara com o instalado; atualizar baixa o APK e o entrega ao
 * instalador do Android, que pede a confirmação (e, na primeira vez, a permissão de instalar).
 */
final class Atualizacao {
    static final String RESULTADO = "com.zervis.voz.INSTALADO";

    private Atualizacao() {}

    static long instalada(Context contexto) {
        try {
            PackageInfo info = contexto.getPackageManager().getPackageInfo(contexto.getPackageName(), 0);
            return info.getLongVersionCode();
        } catch (PackageManager.NameNotFoundException erro) {
            return 0;
        }
    }

    static String nome(Context contexto) {
        try {
            String nome = contexto.getPackageManager().getPackageInfo(contexto.getPackageName(), 0).versionName;
            return nome != null ? nome : "";
        } catch (PackageManager.NameNotFoundException erro) {
            return "";
        }
    }

    /** O número da última versão publicada. */
    static long publicada() throws IOException {
        HttpURLConnection c = abrir(BuildConfig.VERSOES + "versao.json");
        try (InputStream entrada = c.getInputStream()) {
            ByteArrayOutputStream tudo = new ByteArrayOutputStream();
            byte[] pedaco = new byte[1024];
            for (int n; (n = entrada.read(pedaco)) > 0; ) tudo.write(pedaco, 0, n);
            return new JSONObject(tudo.toString("UTF-8")).getLong("codigo");
        } catch (JSONException erro) {
            throw new IOException("Resposta inesperada da atualização.");
        } finally {
            c.disconnect();
        }
    }

    /** Baixa o APK novo e o entrega ao instalador; o resultado volta à tela (RESULTADO). */
    static void instalar(Context contexto) throws IOException {
        PackageInstaller instalador = contexto.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(
                PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName(contexto.getPackageName());
        int id = instalador.createSession(params);
        HttpURLConnection c = abrir(BuildConfig.VERSOES + "ze-voz.apk");
        try (PackageInstaller.Session sessao = instalador.openSession(id)) {
            try (InputStream entrada = c.getInputStream();
                 OutputStream saida = sessao.openWrite("ze-voz.apk", 0, c.getContentLengthLong())) {
                byte[] pedaco = new byte[65536];
                for (int n; (n = entrada.read(pedaco)) > 0; ) saida.write(pedaco, 0, n);
                sessao.fsync(saida);
            }
            Intent volta = new Intent(contexto, MainActivity.class).setAction(RESULTADO);
            PendingIntent aviso = PendingIntent.getActivity(contexto, 0, volta,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE);
            sessao.commit(aviso.getIntentSender());
        } catch (IOException | RuntimeException erro) {
            instalador.abandonSession(id);
            throw erro;
        } finally {
            c.disconnect();
        }
    }

    private static HttpURLConnection abrir(String endereco) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(endereco).openConnection();
        c.setConnectTimeout(10000);
        c.setReadTimeout(30000);
        c.setInstanceFollowRedirects(true); // o GitHub manda o arquivo de outro endereço (HTTPS)
        int status = c.getResponseCode();
        if (status != 200) {
            c.disconnect();
            throw new IOException("Atualização indisponível (" + status + ").");
        }
        return c;
    }
}
