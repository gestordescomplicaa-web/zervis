package com.zervis.voz;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * O que o app guarda: o endereço do Zé, a chave só de voz do pareamento, o modo de ouvir, a escuta
 * de perto e o nível mínimo dela, a saída sem fone (alto-falante ou orelha), os aparelhos
 * Bluetooth em que o microfone é o do celular e quando procurou atualização.
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

    /** Pelo microfone do celular, só passa quem fala junto dele (ADR 0086). Ligada por padrão. */
    boolean perto() { return p.getBoolean("perto", true); }
    void perto(boolean ligar) { p.edit().putBoolean("perto", ligar).apply(); }

    /** O nível mínimo da escuta de perto (Proximidade.MENOR a MAIOR). */
    int nivelPerto() { return p.getInt("nivel_perto", Proximidade.PADRAO); }
    void nivelPerto(int nivel) { p.edit().putInt("nivel_perto", nivel).apply(); }

    /** Sem fone, a fala sai no fone da orelha (o celular no ouvido, como numa ligação). */
    boolean orelha() { return p.getBoolean("orelha", false); }
    void orelha(boolean usar) { p.edit().putBoolean("orelha", usar).apply(); }

    long procurouEm() { return p.getLong("procurou_em", 0); }
    void procurou(long quando) { p.edit().putLong("procurou_em", quando).apply(); }
}
