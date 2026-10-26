package com.zervis.voz;

import android.content.Context;
import android.content.SharedPreferences;

/** O que o app guarda: o endereço do Zé, a chave só de voz do pareamento e o modo de ouvir. */
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
}
