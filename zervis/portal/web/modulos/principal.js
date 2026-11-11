// A entrada do painel. Os módulos se importam uns aos outros; só depois que todos carregaram a
// navegação abre a primeira página e o batimento começa.
import "../painel.js";
import "./voz.js";
import "./imersao.js";
import "./acoes.js";
import { iniciarNavegacao } from "./navegacao.js";

iniciarNavegacao();
