import { camposPerfil, prepararAcesso } from "../modulos/modelos.js";
import { PAGINAS, api, botao, cabeca, cartao, sub } from "../painel.js";
import { compartilhado } from "../modulos/estado.js";

// Página configurar, carregada sob demanda.
PAGINAS.configurar = async function() {
    const [cfg, esc_, ct] = await Promise.all([api("configuracao"), api("escuta"), api("contas")]);
    compartilhado.escuta = esc_;
    compartilhado.contasTela = ct;
    prepararAcesso(cfg);
    const passos = ["Perfil", "Agente", "Reconhecimento de fala"];
    const trilha = `<ol class="passos">${passos.map((t, i) => `<li ${i + 1 === compartilhado.passo ? 'aria-current="step"' : i + 1 < compartilhado.passo ? 'class="feito"' : ""}><span>${i + 1}</span>${t}</li>`).join("")}</ol>`;
    const voltar = compartilhado.passo > 1 ? botao("Voltar", "passo", `data-passo="${compartilhado.passo - 1}"`, "discreta") : "";
    const corpo = {
      1: cartao("Perfil", `${sub("Como o Zé chama você e o que deve saber sobre o seu trabalho.")}${camposPerfil(cfg)}<p class="resultado" id="resultado-perfil"></p>`),
      2: '<section class="cartao" id="cartao-acesso"></section><section class="cartao" id="cartao-contas"></section>',
      3: '<section class="cartao" id="cartao-escuta"></section>',
    }[compartilhado.passo];
    const seguir = compartilhado.passo === 1 ? botao("Continuar", "perfil-salvar", 'data-seguir="2"', "principal")
      : compartilhado.passo === 2 ? botao("Continuar", "passo", 'data-passo="3"', "principal")
      : botao("Concluir", "configuracao-concluir", "", "principal");
    return `${cabeca("Configuração inicial")}${sub("Tudo pode ser alterado depois em Ajustes.")}${trilha}${corpo}
      <div class="linha rodape-passos">${voltar}<span class="espaco"></span>${seguir}</div>`;
  };
