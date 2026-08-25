"""zerolith · « Serverless ou pas ? » — la page, et rien que la page.

Cette fonction n'a AUCUNE base attachée. Elle n'a pas de DATABASE_URL, elle ne
saurait pas quoi en faire : elle rend un document HTML complet et se rendort. C'est
ce qui lui permet de répondre en ~2 s à froid et en quelques dizaines de
millisecondes ensuite.

Toute la partie qui a besoin de mémoire — enregistrer un score, agréger les
statistiques — vit dans la fonction jumelle `quiz-api`, qui elle a une base.

Le tour de passe-passe tient en une ligne de JavaScript, exécutée à la première
image du rendu : la page appelle `quiz-api/wake` sans attendre la réponse. Ce seul
appel réveille le pod de la base et sa restauration depuis le stockage objet — une
dizaine de secondes — pendant que le joueur lit les règles et répond aux dix
questions. Quand il soumet son score, ~45 s plus tard, la base est debout depuis
longtemps et l'écriture prend quelques millisecondes.

Le démarrage à froid n'a pas été supprimé ni raccourci. Il a été déplacé hors du
chemin que quelqu'un attend. `?prewarm=0` désactive l'appel de réveil et rend la
même partie sans le tour de passe-passe : c'est la comparaison, jouable.
"""

import os

# La page a besoin de savoir où joindre son API. Par défaut on la déduit de notre
# propre nom d'hôte — `jeu-fn-<id>` et `quiz-api-fn-<id>` ne diffèrent que par leur
# premier segment — ce qui permet de redéployer la paire sous un autre compte sans
# rien reconfigurer. QUIZ_API_URL reprend la main si les noms diffèrent.
API_ENV = "QUIZ_API_URL"
UI_NAME = "jeu"
API_NAME = "quiz-api"


def _api_url(request):
    explicit = os.environ.get(API_ENV)
    if explicit:
        return explicit.rstrip("/")
    # Le shim rend les en-tetes dans un dict ORDINAIRE, en conservant la casse que
    # werkzeug produit (`Host`). Une recherche sur "host" y echoue donc en silence,
    # et la page repondait 500 en production alors que le banc de test, qui fabrique
    # ses en-tetes en minuscules, restait vert. On normalise la casse ici.
    headers = {k.lower(): v for k, v in (request.headers or {}).items()}
    host = (headers.get("host") or "").split(":")[0]
    if host.startswith(UI_NAME + "-"):
        return "https://" + API_NAME + "-" + host[len(UI_NAME) + 1 :]
    return ""


PAGE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Serverless ou pas ? — zerolith</title>
<meta name="description" content="Un quiz de dix questions qui masque, pendant que vous jouez, le demarrage a froid d'une base de donnees serverless.">
<meta name="robots" content="index, follow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
:root{
  --void:#04060a; --void-2:#080c12; --line:#16212e; --line-soft:#0f1822;
  --amber:#ff8a1e; --cyan:#2de2e6; --cyan-dim:#1b8a8d; --green:#39ff9c; --red:#ff3b3b;
  --ink:#c9d6e2; --ink-dim:#8497a6; --ink-faint:#5b6c7b;
  --mono:'Share Tech Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --display:'Rajdhani','Share Tech Mono',system-ui,sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--void); color:var(--ink); font-family:var(--mono);
  font-size:16px; line-height:1.6; min-height:100vh;
  background-image:radial-gradient(ellipse 80% 50% at 50% -10%,rgba(45,226,230,.07),transparent 70%);
}
.wrap{max-width:760px;margin:0 auto;padding:28px 20px 64px}
header{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;
  border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:26px}
.brand{font-family:var(--display);font-weight:700;letter-spacing:.14em;text-transform:uppercase;
  font-size:15px;color:var(--ink-dim)}
.brand b{color:var(--cyan);font-weight:700}
/* Le badge de la base : le seul endroit de la page qui dit la verite sur ce qui
   se passe en coulisse pendant que vous jouez. */
.db{display:flex;align-items:center;gap:9px;font-size:13px;color:var(--ink-dim);
  border:1px solid var(--line);padding:6px 11px;white-space:nowrap}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ink-faint);flex:none}
.db[data-s=waking] .dot{background:var(--amber);animation:pulse 1s ease-in-out infinite}
.db[data-s=ready] .dot{background:var(--green);box-shadow:0 0 8px rgba(57,255,156,.6)}
.db[data-s=off] .dot{background:var(--red)}
.db[data-s=ready]{color:var(--ink)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
h1{font-family:var(--display);font-size:clamp(30px,7vw,46px);line-height:1.05;margin:0 0 14px;
  letter-spacing:.02em;text-transform:uppercase}
h1 em{font-style:normal;color:var(--cyan)}
.lede{color:var(--ink-dim);margin:0 0 26px;max-width:56ch}
.panel{border:1px solid var(--line);background:var(--void-2);padding:22px}
.rules{list-style:none;margin:0 0 22px;padding:0}
.rules li{padding:7px 0 7px 24px;position:relative;color:var(--ink-dim)}
.rules li::before{content:'>';position:absolute;left:0;color:var(--cyan-dim)}
button{font-family:var(--mono);font-size:15px;cursor:pointer;border:1px solid var(--cyan);
  background:transparent;color:var(--cyan);padding:12px 26px;letter-spacing:.08em;
  text-transform:uppercase;transition:background .12s,color .12s}
button:hover:not(:disabled){background:var(--cyan);color:var(--void)}
button:disabled{cursor:default;opacity:.4}
.meta{display:flex;justify-content:space-between;font-size:13px;color:var(--ink-faint);
  margin-bottom:10px;letter-spacing:.06em}
/* La barre de temps: 8 s par question, purement CSS pour ne pas dependre du JS. */
.bar{height:2px;background:var(--line);margin-bottom:26px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--cyan);width:100%;transform-origin:left}
.bar.run i{animation:drain 8s linear forwards}
@keyframes drain{to{transform:scaleX(0)}}
.q{font-family:var(--display);font-size:clamp(20px,4.4vw,27px);line-height:1.3;margin:0 0 26px;
  min-height:3.2em;display:flex;align-items:center}
.choices{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.choices button{padding:16px;font-size:16px}
.b-false{border-color:var(--amber);color:var(--amber)}
.b-false:hover:not(:disabled){background:var(--amber);color:var(--void)}
.verdict{margin-top:22px;border-left:2px solid var(--line);padding:2px 0 2px 16px;
  color:var(--ink-dim);font-size:14.5px}
.verdict.ok{border-color:var(--green)} .verdict.ko{border-color:var(--red)}
.verdict b{display:block;font-family:var(--display);letter-spacing:.1em;text-transform:uppercase;
  font-size:13px;margin-bottom:5px}
.verdict.ok b{color:var(--green)} .verdict.ko b{color:var(--red)}
.verdict button{display:block;margin-top:16px;padding:9px 20px;font-size:14px}
.score{font-family:var(--display);font-size:clamp(52px,13vw,84px);line-height:1;
  color:var(--cyan);margin:0 0 4px}
.score span{color:var(--ink-faint);font-size:.42em}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);margin:24px 0}
.cell{background:var(--void-2);padding:14px 16px}
.cell k{display:block;font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink-faint);margin-bottom:5px}
.cell v{font-family:var(--display);font-size:22px;color:var(--ink)}
.cell v.hot{color:var(--green)} .cell v.cold{color:var(--amber)}
.reveal{border:1px solid var(--cyan-dim);padding:20px;margin-top:26px;
  background:linear-gradient(180deg,rgba(45,226,230,.05),transparent)}
.reveal h2{font-family:var(--display);text-transform:uppercase;letter-spacing:.1em;font-size:14px;
  color:var(--cyan);margin:0 0 12px}
.reveal p{margin:0 0 12px;font-size:14.5px;color:var(--ink-dim)}
.reveal p:last-child{margin-bottom:0}
.reveal b{color:var(--ink)}
footer{margin-top:34px;padding-top:18px;border-top:1px solid var(--line);
  font-size:13px;color:var(--ink-faint);display:flex;gap:18px;flex-wrap:wrap;justify-content:space-between}
a{color:var(--cyan-dim);text-decoration:none;border-bottom:1px solid transparent}
a:hover{border-bottom-color:var(--cyan-dim)}
.hidden{display:none!important}
@media(max-width:520px){.choices{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="brand">zero<b>lith</b> · demo</div>
  <div class="db" id="db" data-s="idle"><i class="dot"></i><span id="dbtxt">base : au repos</span></div>
</header>

<section id="intro">
  <h1>Serverless<br><em>ou pas ?</em></h1>
  <p class="lede">Dix affirmations sur le cloud sans serveur. Vrai ou faux, huit secondes chacune.
    Pendant que vous lisez ces lignes, il se passe quelque chose ; on vous dira quoi à la fin.</p>
  <div class="panel">
    <ul class="rules">
      <li>10 questions, 8 secondes par question</li>
      <li>une seconde de reflexion vaut mieux qu'un point</li>
      <li>votre score part dans une base de donnees partagee avec tous les joueurs</li>
    </ul>
    <button id="start">Commencer</button>
  </div>
</section>

<section id="play" class="hidden">
  <div class="meta"><span id="pos">question 1 / 10</span><span id="run">0 bonne reponse</span></div>
  <div class="bar" id="bar"><i></i></div>
  <div class="panel">
    <p class="q" id="qtext"></p>
    <div class="choices">
      <button id="btrue">Vrai</button>
      <button id="bfalse" class="b-false">Faux</button>
    </div>
    <div class="verdict hidden" id="verdict"><b id="vtitle"></b><span id="vtext"></span>
      <button id="next" class="hidden">Suivant</button></div>
  </div>
</section>

<section id="done" class="hidden">
  <p class="score"><span id="final">0</span><span>/10</span></p>
  <p class="lede" id="verdictline"></p>
  <div class="grid" id="cells"></div>
  <div class="reveal">
    <h2>Ce que vous n'avez pas vu</h2>
    <div id="story"></div>
  </div>
  <p style="margin-top:24px"><button id="again">Rejouer</button></p>
</section>

<footer>
  <span id="modeline"></span>
  <span><a href="https://zerolith.io">zerolith.io</a></span>
</footer>

</div>

<script>
const API = "__API__";
const PREWARM = !/[?&]prewarm=0/.test(location.search);
const TIME_PER_Q = 8000, REVEAL_MS = 2400;
// Sur une mauvaise reponse on n'enchaine plus tout seul : c'est la seule
// explication que le joueur n'avait pas devinee, donc la seule qu'il faut avoir le
// temps de lire. Le bouton s'active apres ce delai — invisible pour qui lit
// vraiment, et il empeche un enchainement instantane de vider le temps de jeu, qui
// est precisement ce qui couvre le reveil de la base.
const MIN_READ_MS = 900;

const QUESTIONS = [
 ["Une fonction qui ne recoit aucun appel pendant une heure ne coute rien en calcul.", true,
  "C'est le scale-to-zero : plus aucun conteneur ne tourne, donc il n'y a plus rien a facturer cote calcul. Seul le stockage reserve continue de compter."],
 ["« Serverless » signifie qu'il n'y a plus de serveur.", false,
  "Il y en a toujours. Ce qui disparait, c'est leur administration : vous ne les dimensionnez plus, vous ne les patchez plus, et vous ne les payez plus a l'heure reservee."],
 ["Un demarrage a froid, c'est surtout le telechargement de l'image du conteneur.", false,
  "Presque jamais : l'image est deja sur la machine. Sur cette plateforme, les 20 s qu'une fonction Python mettait a repondre venaient d'un plafond CPU trop bas. Une fois corrige : 2 s."],
 ["Garder une instance chaude en permanence supprime le demarrage a froid.", true,
  "Oui, et ca se facture : une instance qui ne dort jamais est une instance que l'on paie tout le temps. C'est un curseur a placer, pas un defaut a corriger."],
 ["Reveiller une base de donnees endormie prend a peu pres le meme temps que reveiller une fonction.", false,
  "Bien plus long : la base doit en plus restaurer son etat depuis le stockage objet. Mesure sur cette plateforme le jour ou cette page a ete ecrite : ~2 s pour la fonction, ~14 s pour la base."],
 ["Une fonction peut garder des donnees en memoire d'un appel au suivant.", false,
  "Elle le fera parfois, et c'est exactement le piege : rien ne le garantit. Le conteneur peut disparaitre entre deux appels, ou l'appel suivant partir sur un autre. Ce qui doit survivre va dans une base."],
 ["Deployer une fonction reconstruit une image Docker a chaque fois.", false,
  "Pas ici : l'image du langage est generique et construite une fois pour toutes, et c'est votre code qui est injecte au demarrage du conteneur. Deployer prend des secondes, pas des minutes."],
 ["Il est normal qu'un appel non authentifie puisse reveiller votre fonction.", false,
  "Surtout pas : le controle doit avoir lieu AVANT le reveil. Sinon n'importe qui sur Internet peut vous faire payer un demarrage a froid, en boucle, sans jamais avoir de compte."],
 ["Le premier visiteur d'une page paie le demarrage a froid, les suivants non.", true,
  "Tant que la fenetre d'inactivite n'est pas ecoulee. C'est ce qui rend le froid difficile a observer quand on teste soi-meme... et facile a oublier le jour de la demonstration."],
 ["Masquer un demarrage a froid, c'est le rendre plus rapide.", false,
  "Non : il dure exactement aussi longtemps. On l'a seulement sorti du chemin ou quelqu'un attend. Regardez le badge en haut de cette page — vous venez d'en traverser un sans le voir."]
];

const $ = id => document.getElementById(id);
const state = {i:0, score:0, answers:[], t0:0, wakeMs:null, wasCold:null, locked:false,
               timer:null, next:null};

/* ---- Le reveil. Lance des la premiere image, jamais attendu. ---------------- */
function wake(){
  if(!PREWARM){
    setDb('off','base : prechauffage desactive');
    $('modeline').textContent = 'mode sans prechauffage — retirez ?prewarm=0 pour comparer';
    return;
  }
  $('modeline').innerHTML = 'prechauffage actif — <a href="?prewarm=0">jouer sans</a>';
  setDb('waking','base : reveil en cours...');
  const t = performance.now();
  fetch(API + '/wake')
    .then(r => r.json())
    .then(d => {
      state.wakeMs = Math.round(performance.now() - t);
      state.wasCold = !!d.was_cold;
      setDb('ready','base : prete en ' + (state.wakeMs/1000).toFixed(1) + ' s');
    })
    .catch(() => setDb('off','base : injoignable'));
}
function setDb(s, txt){ $('db').dataset.s = s; $('dbtxt').textContent = txt; }

/* ---- La partie ------------------------------------------------------------- */
function show(id){ ['intro','play','done'].forEach(s => $(s).classList.toggle('hidden', s !== id)); }

function ask(){
  const [text] = QUESTIONS[state.i];
  $('pos').textContent = 'question ' + (state.i+1) + ' / ' + QUESTIONS.length;
  $('run').textContent = state.score + (state.score > 1 ? ' bonnes reponses' : ' bonne reponse');
  $('qtext').textContent = text;
  $('verdict').classList.add('hidden');
  $('next').classList.add('hidden');
  state.next = null;
  $('btrue').disabled = $('bfalse').disabled = false;
  state.locked = false;
  const bar = $('bar');
  bar.classList.remove('run'); void bar.offsetWidth; bar.classList.add('run');
  state.timer = setTimeout(() => answer(null), TIME_PER_Q);
}

function answer(said){
  if(state.locked) return;
  state.locked = true;
  clearTimeout(state.timer);
  $('bar').classList.remove('run');
  $('btrue').disabled = $('bfalse').disabled = true;

  const [, truth, why] = QUESTIONS[state.i];
  const ok = said === truth;
  state.answers.push(ok);
  if(ok) state.score++;

  const v = $('verdict');
  v.className = 'verdict ' + (ok ? 'ok' : 'ko');
  $('vtitle').textContent = ok ? 'exact' : (said === null ? 'trop tard' : 'rate');
  $('vtext').textContent = why;

  state.i++;
  const goOn = () => state.i < QUESTIONS.length ? ask() : finish();
  if(ok){
    // Bonne reponse : la justification ne fait que confirmer, on enchaine.
    setTimeout(goOn, REVEAL_MS);
    return;
  }
  const next = $('next');
  next.classList.remove('hidden');
  next.disabled = true;
  setTimeout(() => { next.disabled = false; }, MIN_READ_MS);
  state.next = goOn;
}

function advance(){
  if(!state.next || $('next').disabled) return;
  const go = state.next;
  state.next = null;
  $('next').classList.add('hidden');
  go();
}

/* ---- La fin : le seul moment ou la page a besoin de la base ----------------- */
function finish(){
  const duration = Math.round(performance.now() - state.t0);
  show('done');
  $('final').textContent = state.score;
  $('verdictline').textContent =
    state.score >= 9 ? 'Vous avez deja paye pour apprendre tout ca.' :
    state.score >= 7 ? 'Solide. Les pieges restants sont les plus chers.' :
    state.score >= 4 ? 'La moyenne — et la moitie des idees recues coutent cher en production.' :
                       'Bonne nouvelle : tout ce qui suit est plus interessant que le score.';

  cells([['duree de la partie', (duration/1000).toFixed(1) + ' s', ''],
         ['ecriture en base', '...', '']]);

  const t = performance.now();
  fetch(API + '/score', {
    // `text/plain` et pas `application/json`, et ce n'est pas un detail de style :
    // un POST en `application/json` n'est PAS une requete « simple » au sens CORS,
    // donc le navigateur envoie d'abord un OPTIONS de controle prealable. Or le
    // runtime de la plateforme n'expose pas OPTIONS a votre handler : Flask y
    // repond lui-meme, sans en-tete CORS, et le navigateur bloque le POST qui
    // suit. En `text/plain` il n'y a pas de controle prealable du tout, et le
    // serveur lit le corps de la meme facon — `request.json()` analyse les octets
    // recus, il ne consulte pas le Content-Type.
    method:'POST', headers:{'content-type':'text/plain;charset=UTF-8'},
    body: JSON.stringify({
      score: state.score, answers: state.answers, duration_ms: duration,
      prewarm: PREWARM ? 1 : 0, wake_ms: state.wakeMs
    })
  }).then(r => r.json()).then(d => {
    // Voici la mesure qui porte toute la demonstration : le temps qu'a reellement
    // pris l'ecriture, vu de la page. Sur une base prechauffee c'est une centaine
    // de millisecondes ; sur une base endormie, une dizaine de secondes d'ecran fige.
    const submitMs = Math.round(performance.now() - t);
    // On ne peut pas connaitre la duree d'une requete avant qu'elle finisse : cette
    // seconde requete, minuscule et sur une base desormais chaude, va la deposer.
    if(d && d.game_id) fetch(API + '/latency', {
      method:'POST', headers:{'content-type':'text/plain;charset=UTF-8'},  // idem : pas de preflight
      body: JSON.stringify({game_id: d.game_id, submit_ms: submitMs})
    }).catch(()=>{});
    cells([
      ['duree de la partie', (duration/1000).toFixed(1) + ' s', ''],
      ['ecriture en base', submitMs + ' ms', submitMs < 1000 ? 'hot' : 'cold'],
      ['reveil de la base', state.wakeMs === null ? 'non lance' : (state.wakeMs/1000).toFixed(1)+' s',
       state.wakeMs === null ? 'cold' : ''],
      ['vous battez', d.rank && d.rank.better_than_percent !== null ? d.rank.better_than_percent + ' %' : '—', '']
    ]);
    story(submitMs, d);
  }).catch(() => {
    cells([['duree de la partie', (duration/1000).toFixed(1)+' s',''],
           ['ecriture en base','echouee','cold']]);
    $('story').innerHTML = '<p>La base n\'a pas repondu. C\'est aussi une demonstration, involontaire.</p>';
  });
}

function cells(rows){
  $('cells').innerHTML = rows.map(([k,v,c]) =>
    '<div class="cell"><k>'+k+'</k><v class="'+c+'">'+v+'</v></div>').join('');
}

function story(submitMs, d){
  const parts = [];
  if(PREWARM && state.wakeMs !== null){
    parts.push('<p>A la premiere image de cette page, avant meme que vous ayez lu le titre, ' +
      'une requete est partie reveiller la base de donnees. Elle a mis <b>' + (state.wakeMs/1000).toFixed(1) +
      ' s</b> : demarrage du conteneur, puis restauration de son etat depuis le stockage objet. ' +
      'Vous ne l\'avez pas attendue — vous lisiez les regles.</p>');
    parts.push('<p>A la fin de la partie, l\'ecriture de votre score a pris <b>' + submitMs + ' ms</b>. ' +
      'Le demarrage a froid n\'a pas ete supprime, ni raccourci d\'une seule milliseconde. ' +
      'Il a ete deplace hors du chemin ou quelqu\'un attend.</p>');
    parts.push('<p>La page que vous lisez est une fonction sans aucune base attachee. ' +
      'Son unique role est de s\'afficher tout de suite. Une seconde fonction, elle, tient la base : ' +
      'c\'est ce decoupage qui rend le tour possible. ' +
      '<a href="?prewarm=0">Rejouer sans le prechauffage</a> pour voir la difference.</p>');
  } else {
    parts.push('<p>Cette partie s\'est jouee <b>sans prechauffage</b>. Aucune requete de reveil n\'a ete ' +
      'envoyee au chargement, donc la base dormait encore quand vous avez soumis votre score : ' +
      'l\'ecriture a pris <b>' + (submitMs/1000).toFixed(1) + ' s</b>, et vous avez attendu, ecran fige.</p>');
    parts.push('<p>C\'est exactement la meme plateforme, le meme code et la meme base. ' +
      'La seule difference tient dans le moment ou la premiere requete part. ' +
      '<a href="?">Rejouer avec le prechauffage</a>.</p>');
  }
  const s = d && d.rank;
  if(s && s.games) parts.push('<p style="color:var(--ink-faint)">' + s.games +
    ' parties enregistrees dans la base a cet instant.</p>');
  $('story').innerHTML = parts.join('');
}

/* ---- Cablage --------------------------------------------------------------- */
$('btrue').onclick  = () => answer(true);
$('bfalse').onclick = () => answer(false);
$('start').onclick = () => { state.t0 = performance.now(); show('play'); ask(); };
$('again').onclick = () => location.reload();
$('next').onclick = advance;
document.addEventListener('keydown', e => {
  if($('play').classList.contains('hidden')) return;
  if(state.next){
    // Pendant une explication, le clavier ne sert plus qu'a passer a la suite.
    if(e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowRight'){ e.preventDefault(); advance(); }
    return;
  }
  if(e.key === 'v' || e.key === 'ArrowLeft') answer(true);
  if(e.key === 'f' || e.key === 'ArrowRight') answer(false);
});

wake();
</script>
</body>
</html>
"""


def handler(request):
    api = _api_url(request)
    if not api:
        return 500, {"error": "impossible de deduire l'URL de l'API; definissez " + API_ENV}
    return (
        200,
        PAGE.replace("__API__", api),
        {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=60"},
    )
