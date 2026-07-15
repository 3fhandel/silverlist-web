const params = new URLSearchParams(location.search);
const downloadId = Number(params.get("download_id"));
document.querySelector("#filename").textContent = params.get("filename") || "Die CSV-Datei";

document.querySelector("#ignore").addEventListener("click", () => window.close());
document.querySelector("#open").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({type: "open-download", downloadId});
  window.close();
});
