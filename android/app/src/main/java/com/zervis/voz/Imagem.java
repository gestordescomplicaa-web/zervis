package com.zervis.voz;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.util.Base64;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Arrays;
import java.util.Comparator;

/**
 * Uma imagem que o Zé manda a quem fala pelo app (ADR 0086): a foto da câmera da impressora, pedida
 * ("me manda uma foto da impressão") ou junto de um aviso (erro, primeira camada, fim). Chega como
 * {"tipo":"imagem","id":...,"titulo":...,"texto":...,"dados":<JPEG em base64>} e vira uma
 * notificação com a foto; tocar abre a foto inteira ({@link ImagemActivity}).
 *
 * As imagens ficam no cache do app (as 10 mais novas): o Android pode limpá-las, e nada sai dele.
 */
final class Imagem {
    static final String CANAL = "imagens";
    static final String ARQUIVO = "arquivo";
    static final String TITULO = "titulo";

    private static final int NOTIFICACAO = 30; // uma por imagem, separadas pela etiqueta (o id)
    private static final int GUARDADAS = 10;
    private static final int LADO_DA_PREVIA = 1024; // a foto na notificação: o Android recusa as grandes

    private Imagem() {
    }

    static void criarCanal(Context c) {
        NotificationChannel canal = new NotificationChannel(CANAL, "Imagens", NotificationManager.IMPORTANCE_HIGH);
        canal.setDescription("Fotos enviadas pelo Zé, como a câmera da impressora.");
        c.getSystemService(NotificationManager.class).createNotificationChannel(canal);
    }

    /** Uma mensagem "imagem" do Zé: grava a foto e mostra a notificação. */
    static void receber(Context c, JSONObject m) {
        String id = m.optString("id").replaceAll("[^a-zA-Z0-9]", "");
        byte[] jpeg;
        try {
            jpeg = Base64.decode(m.optString("dados"), Base64.DEFAULT);
        } catch (IllegalArgumentException invalida) {
            return;
        }
        if (id.isEmpty() || jpeg.length == 0) return;
        File arquivo;
        try {
            arquivo = gravar(c, id, jpeg);
        } catch (IOException semEspaco) {
            return;
        }
        Bitmap previa = previa(arquivo);
        if (previa == null) return; // não era uma imagem
        String titulo = m.optString(TITULO, "Imagem do Zé");
        String texto = m.optString("texto");
        Intent abrir = new Intent(c, ImagemActivity.class)
                .setData(Uri.fromFile(arquivo)) // um PendingIntent por imagem
                .putExtra(ARQUIVO, arquivo.getAbsolutePath())
                .putExtra(TITULO, titulo)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        Notification n = new Notification.Builder(c, CANAL)
                .setSmallIcon(R.drawable.ic_ze)
                .setContentTitle(titulo)
                .setContentText(texto.isEmpty() ? "Toque para ver." : texto)
                .setLargeIcon(previa)
                .setStyle(new Notification.BigPictureStyle().bigPicture(previa).setSummaryText(texto.isEmpty() ? null : texto))
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setShowWhen(true)
                .setAutoCancel(true)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setPublicVersion(new Notification.Builder(c, CANAL)
                        .setSmallIcon(R.drawable.ic_ze)
                        .setContentTitle("Imagem do Zé")
                        .build())
                .setContentIntent(PendingIntent.getActivity(c, 0, abrir, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT))
                .build();
        c.getSystemService(NotificationManager.class).notify(id, NOTIFICACAO, n);
    }

    private static File gravar(Context c, String id, byte[] jpeg) throws IOException {
        File pasta = new File(c.getCacheDir(), CANAL);
        if (!pasta.isDirectory() && !pasta.mkdirs()) throw new IOException("sem a pasta");
        File arquivo = new File(pasta, id + ".jpg");
        try (FileOutputStream saida = new FileOutputStream(arquivo)) {
            saida.write(jpeg);
        }
        File[] todas = pasta.listFiles();
        if (todas != null && todas.length > GUARDADAS) {
            Arrays.sort(todas, Comparator.comparingLong(File::lastModified));
            for (int i = 0; i < todas.length - GUARDADAS; i++) //noinspection ResultOfMethodCallIgnored
                todas[i].delete();
        }
        return arquivo;
    }

    /** A foto reduzida, para a notificação (e a tela, com um lado maior). */
    static Bitmap carregar(File arquivo, int lado) {
        BitmapFactory.Options medidas = new BitmapFactory.Options();
        medidas.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(arquivo.getAbsolutePath(), medidas);
        if (medidas.outWidth <= 0 || medidas.outHeight <= 0) return null;
        BitmapFactory.Options opcoes = new BitmapFactory.Options();
        opcoes.inSampleSize = 1;
        while (Math.max(medidas.outWidth, medidas.outHeight) / (opcoes.inSampleSize * 2) >= lado) opcoes.inSampleSize *= 2;
        return BitmapFactory.decodeFile(arquivo.getAbsolutePath(), opcoes);
    }

    private static Bitmap previa(File arquivo) {
        return carregar(arquivo, LADO_DA_PREVIA);
    }
}
