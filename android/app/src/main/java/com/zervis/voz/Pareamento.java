package com.zervis.voz;

import android.os.Build;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/** Troca o código que o painel mostra pela chave só de voz (POST /voz-app/parear). */
final class Pareamento {
    private Pareamento() {}

    /** "ze.exemplo.com.br" ou "https://ze.exemplo.com.br/" vira "https://ze.exemplo.com.br". */
    static String endereco(String digitado) {
        String e = digitado.trim().toLowerCase(Locale.ROOT);
        if (!e.startsWith("http://") && !e.startsWith("https://")) e = "https://" + e;
        while (e.endsWith("/")) e = e.substring(0, e.length() - 1);
        return e;
    }

    static String parear(String endereco, String codigo) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(endereco + "/voz-app/parear").openConnection();
        c.setConnectTimeout(10000);
        c.setReadTimeout(15000);
        c.setRequestMethod("POST");
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        byte[] corpo;
        try {
            corpo = new JSONObject()
                    .put("codigo", codigo)
                    .put("nome", Build.MANUFACTURER + " " + Build.MODEL)
                    .toString()
                    .getBytes(StandardCharsets.UTF_8);
        } catch (JSONException erro) {
            throw new IOException(erro);
        }
        try (OutputStream saida = c.getOutputStream()) {
            saida.write(corpo);
        }
        int status = c.getResponseCode();
        String resposta = ler(status < 400 ? c.getInputStream() : c.getErrorStream());
        c.disconnect();
        try {
            JSONObject dados = new JSONObject(resposta);
            if (status == 200) return dados.getString("chave");
            throw new IOException(dados.optString("erro", "O Zé recusou (" + status + ")."));
        } catch (JSONException erro) {
            throw new IOException("Esse endereço não é um Zé (" + status + ").");
        }
    }

    private static String ler(InputStream entrada) throws IOException {
        if (entrada == null) return "";
        ByteArrayOutputStream tudo = new ByteArrayOutputStream();
        byte[] pedaco = new byte[4096];
        for (int n; (n = entrada.read(pedaco)) > 0; ) tudo.write(pedaco, 0, n);
        entrada.close();
        return tudo.toString("UTF-8");
    }
}
