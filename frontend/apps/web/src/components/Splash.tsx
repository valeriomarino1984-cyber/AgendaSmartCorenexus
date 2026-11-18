import { APP_NAME } from "@/lib/brand";
import { LogoMark } from "./Logo";

/**
 * Apertura della home: il logo compare, la spunta si disegna, una barra si riempie e la pagina si scopre.
 * Solo CSS (nessun ritardo nel caricamento reale). Con "riduci movimento" compare fermo e sparisce in dissolvenza.
 */
export function Splash() {
  return (
    <div className="splash" aria-hidden>
      <div className="splash-inner">
        <LogoMark className="splash-logo" animated />
        <p className="splash-name">{APP_NAME}</p>
        <span className="splash-bar">
          <span />
        </span>
      </div>
    </div>
  );
}
