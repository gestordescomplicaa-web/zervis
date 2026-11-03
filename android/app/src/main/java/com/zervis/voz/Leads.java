package com.zervis.voz;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.service.notification.StatusBarNotification;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * Os leads do WhatsApp esperando a sua resposta (ADR 0053): o Zé manda a lista inteira a cada
 * mudança ({"tipo":"whatsapp","leads":[...]}) e aqui cada lead vira uma notificação, com a
 * etiqueta do id dele. Lead novo toca; o lembrete (o número de lembretes subiu) toca de novo; texto
 * novo do mesmo lead só atualiza; o que saiu da lista (respondido) some.
 *
 * Os botões: "Ouvir" pede ao Zé a mensagem falada, "Abrir no WhatsApp" abre a conversa (quando o
 * número é conhecido) e "Já vi" para os lembretes. Arrastar a notificação para o lado vale como
 * "Já vi". Na tela bloqueada, sem o conteúdo: só "Mensagem importante no WhatsApp". Também vêm aqui
 * as mensagens de quem está na lista de prioridade e as respostas ao que o Zé mandou (ADR 0055).
 */
final class Leads {
    static final String CANAL = "leads";
    static final String OUVIR = "lead_ouvir";
    static final String VISTO = "lead_visto";
    static final String ID_DO_LEAD = "id";

    private static final int NOTIFICACAO = 10; // uma por lead, separadas pela etiqueta (o id)
    private static final String LEMBRETES = "ze.lembretes";

    private Leads() {
    }

    static void criarCanal(Context c) {
        NotificationChannel canal = new NotificationChannel(CANAL, "Leads do WhatsApp", NotificationManager.IMPORTANCE_HIGH);
        canal.setDescription("Leads qualificados esperando a sua resposta.");
        c.getSystemService(NotificationManager.class).createNotificationChannel(canal);
    }

    static void mostrar(Context c, JSONArray leads) {
        NotificationManager avisos = c.getSystemService(NotificationManager.class);
        // O que já está na barra (inclusive de antes de o app reiniciar): sem tocar de novo à toa.
        Map<String, Integer> antes = new HashMap<>();
        for (StatusBarNotification n : avisos.getActiveNotifications()) {
            if (n.getId() == NOTIFICACAO && n.getTag() != null) {
                antes.put(n.getTag(), n.getNotification().extras.getInt(LEMBRETES, -1));
            }
        }
        Set<String> agora = new HashSet<>();
        for (int i = 0; i < leads.length(); i++) {
            JSONObject lead = leads.optJSONObject(i);
            String id = lead != null ? lead.optString("id") : "";
            if (id.isEmpty()) continue;
            agora.add(id);
            int lembretes = lead.optInt("lembretes");
            Integer visto = antes.get(id);
            avisos.notify(id, NOTIFICACAO, notificacao(c, lead, lembretes, visto == null || lembretes > visto));
        }
        for (String id : antes.keySet()) {
            if (!agora.contains(id)) avisos.cancel(id, NOTIFICACAO);
        }
    }

    static void apagar(Context c, String id) {
        c.getSystemService(NotificationManager.class).cancel(id, NOTIFICACAO);
    }

    private static Notification notificacao(Context c, JSONObject lead, int lembretes, boolean tocar) {
        String id = lead.optString("id");
        String nome = lead.optString("nome", "Contato");
        String texto = lead.optString("texto");
        // Lead qualificado, Prioridade (a lista do Zé) ou Respondeu (ao que o Zé mandou por você).
        String motivo = lead.optString("motivo", "Lead qualificado");
        Bundle extras = new Bundle();
        extras.putInt(LEMBRETES, lembretes);
        Notification.Builder b = new Notification.Builder(c, CANAL)
                .setSmallIcon(R.drawable.ic_ze)
                .setContentTitle(nome)
                .setContentText(texto)
                .setStyle(new Notification.BigTextStyle().bigText(texto))
                .setSubText(lembretes > 0 ? motivo + " · esperando resposta" : motivo)
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setWhen(lead.optLong("chegou", System.currentTimeMillis()))
                .setShowWhen(true)
                .setOnlyAlertOnce(!tocar)
                .setGroup(CANAL)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setPublicVersion(new Notification.Builder(c, CANAL)
                        .setSmallIcon(R.drawable.ic_ze)
                        .setContentTitle("Mensagem importante no WhatsApp")
                        .build())
                .addExtras(extras)
                .setDeleteIntent(paraOZe(c, VISTO, id))
                .addAction(new Notification.Action.Builder(null, "Ouvir", paraOZe(c, OUVIR, id)).build());
        PendingIntent abrir = abrirConversa(c, lead.optString("telefone"));
        if (abrir != null) {
            b.setContentIntent(abrir);
            b.addAction(new Notification.Action.Builder(null, "Abrir no WhatsApp", abrir).build());
        }
        b.addAction(new Notification.Action.Builder(null, "Já vi", paraOZe(c, VISTO, id)).build());
        return b.build();
    }

    private static PendingIntent paraOZe(Context c, String acao, String id) {
        Intent intent = new Intent(c, VozService.class)
                .setAction(acao)
                .setData(Uri.parse("zervis-voz://lead/" + Uri.encode(id))) // um PendingIntent por lead
                .putExtra(ID_DO_LEAD, id);
        return PendingIntent.getService(c, 0, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    /** A conversa no WhatsApp (ou no WhatsApp Business: o Android pergunta qual), pelo número. */
    private static PendingIntent abrirConversa(Context c, String telefone) {
        if (!telefone.matches("\\d{8,15}")) return null;
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/" + telefone))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        return PendingIntent.getActivity(c, 0, intent, PendingIntent.FLAG_IMMUTABLE);
    }
}
