// A entrada do painel. Os módulos se importam uns aos outros; só depois que todos carregaram a
// navegação abre a primeira página e o batimento começa.
import "../painel.js";
import "./voz.js";
import "./imersao.js";
import "./acoes.js";
import "./casca.js";
import { iniciarNavegacao } from "./navegacao.js";

iniciarNavegacao();
import("./avisos.js"); // o sino e a central de avisos, logo depois da abertura
