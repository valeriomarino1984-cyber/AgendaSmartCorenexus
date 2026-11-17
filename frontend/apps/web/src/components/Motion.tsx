/**
 * Comparsa allo scorrimento (dalla home di Presenze): titoli e blocchi entrano con una dissolvenza dal basso,
 * i figli dei contenitori con data-stagger uno dopo l'altro; data-spot attiva l'alone che segue il puntatore.
 * Script minimo in pagina, nessun pacchetto. Se manca IntersectionObserver o è attivo "riduci movimento"
 * non nasconde nulla. Va messo in fondo a <main>, quando gli elementi esistono già.
 */
const script = `(function(){try{
var mq=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)");
if(!("IntersectionObserver" in window)||(mq&&mq.matches))return;
var root=document.querySelector("main");if(!root)return;
var targets=[];
root.querySelectorAll("main > section:not(:first-child)").forEach(function(s){
  s.querySelectorAll("h2, h2 + p").forEach(function(el){targets.push([el,0])});
});
root.querySelectorAll("[data-reveal]").forEach(function(el){targets.push([el,0])});
root.querySelectorAll("[data-stagger]").forEach(function(c){Array.prototype.forEach.call(c.children,function(el,i){targets.push([el,Math.min(i,8)*90])})});
var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.setAttribute("data-in","");io.unobserve(e.target)}})},{rootMargin:"0px 0px -8% 0px",threshold:0.12});
targets.forEach(function(t){var el=t[0];if(el.hasAttribute("data-r"))return;el.setAttribute("data-r","");if(t[1])el.style.setProperty("--rd",t[1]+"ms");io.observe(el)});
document.documentElement.setAttribute("data-motion","");
root.querySelectorAll("[data-spot]").forEach(function(el){el.addEventListener("pointermove",function(ev){var r=el.getBoundingClientRect();el.style.setProperty("--mx",(ev.clientX-r.left)+"px");el.style.setProperty("--my",(ev.clientY-r.top)+"px")})});
setTimeout(function(){targets.forEach(function(t){t[0].setAttribute("data-in","")})},12000);
}catch(e){}})();`;

export function Motion() {
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
