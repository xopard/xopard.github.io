// Añade tu sesión de Strava (sus cookies) a las teselas del mapa de calor que pide xopard.github.io.
// Es lo mismo que hace la extensión «Strava Heatmap» para gpx.studio, pero para esta web.
// Las cookies no salen de tu navegador: solo se envían a strava.com, que es quien las emitió.
const COOKIES = ["_strava_idcf", "CloudFront-Key-Pair-Id", "CloudFront-Policy", "CloudFront-Signature"];
const LOGIN = "https://www.strava.com/maps/global-heatmap";

async function credenciales() {
  const valores = await Promise.all(COOKIES.map(name => chrome.cookies.get({ url: "https://www.strava.com", name })));
  if (valores.some(c => !c || !c.value)) return null;
  return valores.map((c, i) => `${COOKIES[i]}=${c.value}`).join("; ");
}

async function actualizar() {
  const cred = await credenciales();
  const reglas = !cred ? [] : [{
    id: 1,
    priority: 1,
    condition: {
      regexFilter: "^https://[^/]+\\.strava\\.com/identified/globalheat/",
      initiatorDomains: ["xopard.github.io"],
      resourceTypes: ["image", "xmlhttprequest"],
    },
    action: {
      type: "modifyHeaders",
      requestHeaders: [{ header: "Cookie", operation: "set", value: cred }],
      responseHeaders: [{ header: "Access-Control-Allow-Origin", operation: "set", value: "*" }],
    },
  }];
  await chrome.declarativeNetRequest.updateDynamicRules({ removeRuleIds: [1], addRules: reglas });
  await chrome.action.setBadgeText({ text: cred ? "" : "!" });
  await chrome.action.setBadgeBackgroundColor({ color: "#d50000" });
  await chrome.action.setTitle({ title: cred
    ? "Mapa de calor de Strava: sesión lista"
    : "Sin sesión de Strava: pulsa para entrar en el mapa de calor de Strava con tu cuenta" });
}

let pendiente = null;
const actualizarLuego = () => { clearTimeout(pendiente); pendiente = setTimeout(actualizar, 500); };
chrome.runtime.onInstalled.addListener(actualizar);
chrome.runtime.onStartup.addListener(actualizar);
chrome.cookies.onChanged.addListener(({ cookie }) => {
  if (cookie.domain.endsWith("strava.com") && COOKIES.includes(cookie.name)) actualizarLuego();
});
chrome.action.onClicked.addListener(() => chrome.tabs.create({ url: LOGIN }));
