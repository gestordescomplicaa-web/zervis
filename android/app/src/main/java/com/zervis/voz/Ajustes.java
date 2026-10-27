package com.zervis.voz;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * O que o app guarda: o endereço do Zé, a chave só de voz do pareamento, o modo de ouvir, os
 * aparelhos Bluetooth em que o microfone é o do celular e quando procurou atualização.
 */
final class Ajustes {
    static final String CHAMADO = "chamado"; // "Ei Zé" e o botão do fone, como o microfone do PC
    static final String AO_VIVO = "ao_vivo"; // cada frase é um pedido

    private final SharedPreferences p;

    Ajustes(Context contexto) {
        p = contexto.getSharedPreferences("ze-voz", Context.MODE_PRIVATE);
    }

    String endereco() { return p.getString("endereco", ""); }
    String chave() { return p.getString("chave", ""); }
    String modo() { return p.getString("modo", CHAMADO); }
    boolean pareado() { return !endereco().isEmpty() && !chave().isEmpty(); }

    void parear(String endereco, String chave) {
        p.edit().putString("endereco", endereco).putString("chave", chave).apply();
    }

    void esquecer() { p.edit().remove("chave").apply(); }

    void modo(String modo) { p.edit().putString("modo", modo).apply(); }

    void trocarModo() { modo(AO_VIVO.equals(modo()) ? CHAMADO : AO_VIVO); }

    /** Neste aparelho (pelo nome), o Zé ouve pelo microfone do celular e fala pelo aparelho. */
    boolean microfoneDoCelular(String aparelho) {
        return p.getStringSet("microfone_do_celular", Collections.emptySet()).contains(aparelho);
    }

    void microfoneDoCelular(String aparelho, boolean usar) {
        Set<String> nomes = new HashSet<>(p.getStringSet("microfone_do_celular", Collections.emptySet()));
        if (usar) nomes.add(aparelho); else nomes.remove(aparelho);
        p.edit().putStringSet("microfone_do_celular", nomes).apply();
    }

    long procurouEm() { return p.getLong("procurou_em", 0); }
    void procurou(long quando) { p.edit().putLong("procurou_em", quando).apply(); }
}
