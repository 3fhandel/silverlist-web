const DEFAULT_URL = "https://sandbox.3f-blb.local/silverlists/";
const input = document.querySelector("#url");
const status = document.querySelector("#status");

chrome.storage.sync.get({silverListsUrl: DEFAULT_URL}).then(({silverListsUrl}) => {
  input.value = silverListsUrl;
});

document.querySelector("#save").addEventListener("click", async () => {
  const url = new URL(input.value);
  if (!/^https?:$/.test(url.protocol)) throw new Error("Nur HTTP oder HTTPS ist erlaubt.");
  await chrome.storage.sync.set({silverListsUrl: url.toString()});
  status.textContent = "Gespeichert";
  setTimeout(() => { status.textContent = ""; }, 1800);
});
