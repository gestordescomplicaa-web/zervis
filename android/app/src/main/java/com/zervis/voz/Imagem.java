package com.zervis.voz;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Date;
import java.util.Locale;

/**
 * Uma imagem que o Zé manda a quem fala pelo app (ADR 0086): a foto da câmera da impressora, pedida
 * ("me manda uma foto da impressão") ou junto de um aviso (erro, primeira camada, fim). Chega como
 * {"tipo":"imagem","id":...,"titulo":...,"texto":...,"dados":<JPEG em base64>} e vira uma
 * notificação com a foto; tocar abre a foto inteira ({@link ImagemActivity}).
 *
 * As imagens ficam no cache do app (as 10 mais novas), para a tela cheia. A foto da câmera da
 * casa ({"salvar":true}, ADR 0087) também vai para a galeria do celular, em Imagens/Zervis, com a
 * hora em que foi tirada ({"quando"}): o celular é a cópia que sai de casa, e ela fica mesmo que
 * o PC seja levado. Na Android 11+ (o mínimo do app), gravar na galeria não pede permissão.
 */
final class Imagem {
    static final String CANAL = "imagens";
    static final String ARQUIVO = "arquivo";
    static final String TITULO = "titulo";
    static final String GALERIA = "galeria"; // a foto salva na galeria (para compartilhar)
    static final String PASTA_DA_GALERIA = Environment.DIRECTORY_PICTURES + "/Zervis";

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
        File arquivo = new File(new File(c.getCacheDir(), CANAL), id + ".jpg");
        if (arquivo.isFile()) return; // a mesma foto de novo (a fila do Zé reenviou): já chegou
        try {
            arquivo = gravar(c, id, jpeg);
        } catch (IOException semEspaco) {
            return;
        }
        Bitmap previa = previa(arquivo);
        if (previa == null) return; // não era uma imagem
        long quando = m.optLong("quando", 0) * 1000;
        if (quando <= 0) quando = System.currentTimeMillis();
        Uri naGaleria = m.optBoolean("salvar") ? salvarNaGaleria(c, id, jpeg, quando) : null;
        String titulo = m.optString(TITULO, "Imagem do Zé");
        String texto = m.optString("texto");
        if (texto.isEmpty() && naGaleria != null) texto = "Salva na galeria.";
        Intent abrir = new Intent(c, ImagemActivity.class)
                .setData(Uri.fromFile(arquivo)) // um PendingIntent por imagem
                .putExtra(ARQUIVO, arquivo.getAbsolutePath())
                .putExtra(TITULO, titulo)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        if (naGaleria != null) abrir.putExtra(GALERIA, naGaleria.toString());
        Notification.Builder n = new Notification.Builder(c, CANAL)
                .setSmallIcon(R.drawable.ic_ze)
                .setContentTitle(titulo)
                .setContentText(texto.isEmpty() ? "Toque para ver." : texto)
                .setLargeIcon(previa)
                .setStyle(new Notification.BigPictureStyle().bigPicture(previa).setSummaryText(texto.isEmpty() ? null : texto))
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setShowWhen(true)
                .setWhen(quando) // a hora em que foi tirada, mesmo se chegou depois
                .setAutoCancel(true)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setPublicVersion(new Notification.Builder(c, CANAL)
                        .setSmallIcon(R.drawable.ic_ze)
                        .setContentTitle("Imagem do Zé")
                        .build())
                .setContentIntent(PendingIntent.getActivity(c, 0, abrir, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
        if (naGaleria != null) {
            PendingIntent enviar = PendingIntent.getActivity(c, id.hashCode(), compartilhar(naGaleria, titulo),
                    PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            n.addAction(new Notification.Action.Builder(null, "Compartilhar", enviar).build());
        }
        c.getSystemService(NotificationManager.class).notify(id, NOTIFICACAO, n.build());
    }

    /** Grava na galeria (Imagens/Zervis), com a data em que foi tirada; null se não deu. */
    static Uri salvarNaGaleria(Context c, String id, byte[] jpeg, long quando) {
        String hora = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date(quando));
        ContentValues v = new ContentValues();
        v.put(MediaStore.Images.Media.DISPLAY_NAME, "Zervis_" + hora + "_" + id + ".jpg");
        v.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
        v.put(MediaStore.Images.Media.RELATIVE_PATH, PASTA_DA_GALERIA);
        v.put(MediaStore.Images.Media.DATE_TAKEN, quando);
        v.put(MediaStore.Images.Media.IS_PENDING, 1);
        ContentResolver r = c.getContentResolver();
        Uri uri = r.insert(MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), v);
        if (uri == null) return null;
        try (OutputStream saida = r.openOutputStream(uri)) {
            if (saida == null) throw new IOException("sem saída");
            saida.write(jpeg);
        } catch (IOException falhou) {
            r.delete(uri, null, null);
            return null;
        }
        ContentValues pronta = new ContentValues();
        pronta.put(MediaStore.Images.Media.IS_PENDING, 0);
        r.update(uri, pronta, null, null);
        return uri;
    }

    /** O "Compartilhar" do Android para uma foto da galeria. */
    static Intent compartilhar(Uri foto, String titulo) {
        Intent enviar = new Intent(Intent.ACTION_SEND)
                .setType("image/jpeg")
                .putExtra(Intent.EXTRA_STREAM, foto)
                .putExtra(Intent.EXTRA_SUBJECT, titulo)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        return Intent.createChooser(enviar, "Compartilhar").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
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
